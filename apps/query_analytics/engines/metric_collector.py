"""
query_analytics.engines.metric_collector
------------------------------------------
Core metric-collection entry points.  Callers (middleware, view decorators,
direct import from connections views) should use:

    from apps.query_analytics.engines.metric_collector import record_metric

All heavy aggregation / time-series rollup is handed off to background
tasks (management commands / Celery equivalent) so that the request thread
is never blocked.
"""
from __future__ import annotations

import time
import psutil
import os
from contextlib import contextmanager

from django.conf import settings
from django.utils import timezone

from apps.query_analytics.models import (
    ConnectionSnapshot,
    MetricAggregate,
    QueryExecutionPlan,
    QueryMetric,
    QueryOptimizationSuggestion,
    SlowQuery,
)
from apps.query_analytics.engines.index_engine    import generate_recommendations
from apps.query_analytics.engines.optimization_engine import generate_suggestions
from apps.query_analytics.engines.plan_parser     import parse


# ---------------------------------------------------------------------------
# Subscription gating
# ---------------------------------------------------------------------------
def _user_can_access_feature(user, feature: str) -> bool:
    """Return True when the user’s subscription tier allows the named feature."""
    try:
        sub = user.subscription_ref
    except Exception:
        return False
    if not sub or not sub.tier:
        return False
    return bool(getattr(sub.tier, f"allow_{feature}", False))


def _should_collect(user, engine: str) -> bool:
    """
    Free tier: only collects for engines the user has connected.
    Pro/Enterprise: always collects.
    """
    try:
        sub = user.subscription_ref
    except Exception:
        return True
    if not sub:
        return True
    tier = getattr(sub.tier, "name", "") if sub.tier else ""
    if tier in ("pro", "enterprise"):
        return True
    # free tier  –  collect but keep limited retention
    return True


# ---------------------------------------------------------------------------
# Core recorder
# ---------------------------------------------------------------------------
def record_metric(
    *,
    user,
    engine: str,
    query_text: str,
    duration_ms: float,
    rows_affected: int = 0,
    connection=None,
    query_history=None,
    success: bool = True,
    error_message: str = "",
    execution_plan_text: str | None = None,
    memory_mb: float | None = None,
    cpu_pct: float | None = None,
    status: str | None = None,
) -> QueryMetric:
    """
    Persist a QueryMetric row and trigger downstream engines.

    This is the single function every part of the codebase should call
    when wrapping a query execution.
    """
    if not _should_collect(user, engine):
        raise PermissionError("Query analytics is not included in your subscription tier.")

    metric_status = status or (MetricStatus.ERROR if not success else MetricStatus.SUCCESS)

    mem = memory_mb if memory_mb is not None else _mem_mb()
    cpu = cpu_pct   if cpu_pct   is not None else _cpu_pct()

    metric = QueryMetric.objects.create(
        user=user,
        connection=connection,
        query_history=query_history,
        engine=engine,
        query_text=query_text[:4000],
        duration_ms=duration_ms,
        rows_affected=rows_affected,
        memory_consumed_mb=mem,
        cpu_percent=cpu,
        status=metric_status,
        error_message=error_message[:1024],
    )

    # Fire async engines (do not block if they fail)
    _engines = settings.QA_TRIGGER_ENGINES
    for eng in _engines:
        try:
            if eng == "slow_query":
                # slow_query_engine.check_threshold(metric)
                from apps.query_analytics.engines.slow_query_engine import check_threshold
                check_threshold(metric)
            elif eng == "alert":
                from apps.query_analytics.engines.alert_engine import check_bottlenecks
                check_bottlenecks(metric)
            elif eng == "optimization" and success and duration_ms > 200:
                from apps.query_analytics.engines.optimization_engine import generate_suggestions
                generate_suggestions(user_id=str(user.id), metric=metric)
            elif eng == "recommendation" and duration_ms > 500:
                generate_recommendations(user_id=str(user.id))
        except Exception:
            pass  # engines must never raise into the caller

    return metric


# ---------------------------------------------------------------------------
# Execution-plan helper
# ---------------------------------------------------------------------------
def record_execution_plan(
    *,
    user,
    engine: str,
    plan_text: str,
    duration_ms: float,
    connection=None,
    **extra,
) -> QueryExecutionPlan:
    parsed = parse(plan_text, engine)
    return QueryExecutionPlan.objects.create(
        user=user,
        engine=engine,
        plan_text=plan_text[:4096],
        parsed_plan=parsed,
        execution_time_ms=duration_ms,
        rows_returned=parsed.get("actual_rows_returned", 0) or 0,
        rows_examined=parsed.get("actual_rows_examined", 0) or 0,
        total_cost=parsed.get("total_cost", 0),
        indexes_used=parsed.get("used_indexes", []),
    )


# ---------------------------------------------------------------------------
# Resource helpers
# ---------------------------------------------------------------------------
def _mem_mb() -> float:
    try:
        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


def _cpu_pct() -> float:
    try:
        proc = psutil.Process(os.getpid())
        return round(proc.cpu_percent(interval=0.01), 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Context-manager decorator  (use as   with timed_query(user, engine) as m: …)
# ---------------------------------------------------------------------------
@contextmanager
def timed_query(user, engine: str, **kwargs):
    """
    Context manager that measures duration and calls record_metric
    on exit.  Accepts all keyword args of record_metric plus:
    - capture_output: bool  – if True, returns (result, cols, metric)
    """
    t0   = time.perf_counter()
    ok   = True
    err  = ""
    rows = 0

    try:
        kwargs.setdefault("rows_affected", 0)
        yield {} if not kwargs.pop("capture_output", False) else _CaptureCtx()
    except Exception as ex:
        ok  = False
        err = str(ex)
        raise
    finally:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        record_metric(
            user=user,
            engine=engine,
            query_text=kwargs.get("query_text", ""),
            duration_ms=duration_ms,
            rows_affected=kwargs.get("rows_affected", rows),
            connection=kwargs.get("connection"),
            query_history=kwargs.get("query_history"),
            success=ok,
            error_message=err,
            execution_plan_text=kwargs.get("execution_plan_text"),
            memory_mb=kwargs.get("memory_mb"),
            cpu_pct=kwargs.get("cpu_pct"),
            status=kwargs.get("status"),
        )


class _CaptureCtx:
    def __init__(self):
        self.cols  = []
        self.rows  = []
        self.metric = None


# ---------------------------------------------------------------------------
# Background / management-command helpers
# ---------------------------------------------------------------------------
def aggregate_metrics(user_id: str, engine: str, granularity: str, bucket_start) -> MetricAggregate:
    """Compute and persist one MetricAggregate row for the given bucket."""
    qs = QueryMetric.objects.filter(
        user_id=user_id, engine=engine,
        executed_at__gte=bucket_start,
    )
    next_ts = {
        "1m":  60, "5m": 300, "15m": 900,
        "1h":  3600, "1d": 86400,
    }.get(granularity, 300)

    bucket_end = bucket_start + __import__("datetime").timedelta(seconds=next_ts)
    qs = qs.filter(executed_at__lt=bucket_end)

    agg, _created = MetricAggregate.objects.get_or_create(
        user_id=user_id, engine=engine, granularity=granularity, bucket_start=bucket_start,
        defaults=dict(
            avg_duration_ms=0, max_duration_ms=0, min_duration_ms=0,
            query_count=0, total_rows=0, avg_memory_mb=0, avg_cpu_pct=0,
            error_count=0, slow_query_count=0,
        ),
    )
    values = qs.aggregate(
        avg  = Avg("duration_ms"),
        mx   = models.Max("duration_ms"),
        mn   = models.Min("duration_ms"),
        cnt  = models.Count("id"),
        rows = models.Sum("rows_affected"),
        mem  = models.Avg("memory_consumed_mb"),
        cpu  = models.Avg("cpu_percent"),
        err  = models.Count("id", filter=models.Q(status=MetricStatus.ERROR)),
    )
    if values["avg"] is not None:
        agg.avg_duration_ms   = round(float(values["avg"]), 2)
        agg.max_duration_ms   = round(float(values["mx"] or 0), 2)
        agg.min_duration_ms   = round(float(values["mn"] or 0), 2)
        agg.query_count       = int(values["cnt"] or 0)
        agg.total_rows        = int(values["rows"] or 0)
        agg.avg_memory_mb     = round(float(values["mem"] or 0), 2)
        agg.avg_cpu_pct       = round(float(values["cpu"] or 0), 2)
        agg.error_count       = int(values["err"] or 0)
        agg.save()
    return agg


from django.db import models  # re-export for use above
