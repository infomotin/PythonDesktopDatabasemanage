"""
query_analytics.engines.metric_collector
------------------------------------------
Core metric-collection entry points.  Callers (view code, management commands)
should use:

    from apps.query_analytics.engines.metric_collector import record_metric

All heavy aggregation is deferred to background tasks / management commands
so the request thread is never blocked.
"""
from __future__ import annotations

import time
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
from apps.query_analytics.engines.index_engine        import generate_recommendations
from apps.query_analytics.engines.optimization_engine import generate_suggestions
from apps.query_analytics.engines.plan_parser         import parse
from apps.query_analytics.engines.slow_query_engine   import check_threshold
from apps.query_analytics.engines.alert_engine        import check_bottlenecks

# ---------------------------------------------------------------------------
# Which sub-engines are active  (comma-separated env var)
# Available: slow_query, alert, optimization, recommendation
# ---------------------------------------------------------------------------
_raw = getattr(settings, "QA_TRIGGER_ENGINES",
               "slow_query,alert,optimization,recommendation")
if isinstance(_raw, str):
    _TRIGGER_ENGINES: list[str] = [e.strip() for e in _raw.split(",") if e.strip()]
else:
    _TRIGGER_ENGINES = list(_raw)


# ---------------------------------------------------------------------------
# Subscription / feature gates
# ---------------------------------------------------------------------------
def _should_collect(user, engine: str) -> bool:
    """Free tier collects basic metrics; Premium/Enterprise always."""
    try:
        sub = user.subscription
    except Exception:
        return True
    if not sub or not sub.tier:
        return True
    tier = sub.tier.name
    return tier in ("pro", "enterprise") or tier == "free"  # always collect; retention differs


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
    Always non-blocking — engine errors are silently swallowed.
    """
    from apps.query_analytics.models import MetricStatus  # avoid circular

    if not _should_collect(user, engine):
        raise PermissionError("Analytics not available on your subscription tier.")

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

    # Fire configured downstream engines — never raise into the caller
    for eng in _TRIGGER_ENGINES:
        try:
            if eng == "slow_query":
                check_threshold(metric)
            elif eng == "alert":
                check_bottlenecks(metric)
            elif eng == "optimization" and success and duration_ms > 200:
                generate_suggestions(user_id=str(user.id), metric=metric)
            elif eng == "recommendation" and duration_ms > float(
                    getattr(settings, "SLOW_QUERY_THRESHOLD_MS", 500)):
                generate_recommendations(user_id=str(user.id))
        except Exception:
            pass

    return metric


# ---------------------------------------------------------------------------
# Execution-plan helper
# ---------------------------------------------------------------------------
def record_execution_plan(
    *,
    user,
    engine: str,
    plan_text: str,
    duration_ms: float = 0,
    connection=None,
    **extra,
) -> QueryExecutionPlan:
    parsed = parse(plan_text, engine)
    return QueryExecutionPlan.objects.create(
        user=user,
        engine=engine,
        plan_text=plan_text[:4096],
        parsed_plan=parsed,
        execution_time_ms=duration_ms or 0,
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
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


def _cpu_pct() -> float:
    try:
        import psutil
        return round(psutil.Process(os.getpid()).cpu_percent(interval=0.001), 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Context manager  usage:
#   with timed_query(user, engine) as cm:
#       result, cols = adapter.execute(sql)
# ---------------------------------------------------------------------------
@contextmanager
def timed_query(user, engine: str, **kwargs):
    """Wraps a block of code, records a QueryMetric on exit."""
    t0   = time.perf_counter()
    ok   = True
    err  = ""
    try:
        yield {}
    except Exception as exc:
        ok  = False
        err = str(exc)
        raise
    finally:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        record_metric(
            user=user,
            engine=engine,
            query_text=kwargs.get("query_text", ""),
            duration_ms=duration_ms,
            rows_affected=kwargs.get("rows_affected", 0),
            connection=kwargs.get("connection"),
            query_history=kwargs.get("query_history"),
            success=ok,
            error_message=err,
        )


# ---------------------------------------------------------------------------
# Background / management-command helper
# ---------------------------------------------------------------------------
def aggregate_metrics(
    user_id: str,
    engine: str,
    granularity: str,
    bucket_start,
) -> MetricAggregate:
    """Compute and persist one MetricAggregate row for the given time bucket."""
    import datetime as _dt_mod

    qs = QueryMetric.objects.filter(
        user_id=user_id, engine=engine, executed_at__gte=bucket_start,
    )
    seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}.get(granularity, 300)
    bucket_end = bucket_start + _dt_mod.timedelta(seconds=seconds)
    qs = qs.filter(executed_at__lt=bucket_end)

    from django.db.models.functions import Max as FMax, Min as FMin, Avg as FAvg, Sum as FSum, Count as FCount
    from django.db.models import Q as FQ

    agg, _ = MetricAggregate.objects.get_or_create(
        user_id=user_id, engine=engine, granularity=granularity, bucket_start=bucket_start,
        defaults=dict(
            avg_duration_ms=0, max_duration_ms=0, min_duration_ms=0,
            query_count=0, total_rows=0, avg_memory_mb=0, avg_cpu_pct=0,
            error_count=0, slow_query_count=0,
        ),
    )
    values = qs.aggregate(
        avg_dur=FAvg("duration_ms"),
        max_dur=FMax("duration_ms"),
        min_dur=FMin("duration_ms"),
        cnt=FCount("id"),
        rows=FSum("rows_affected"),
        mem=FAvg("memory_consumed_mb"),
        cpu=FAvg("cpu_percent"),
        err=FCount("id", filter=FQ(status="error")),
    )
    if values["avg_dur"] is not None:
        agg.avg_duration_ms   = round(float(values["avg_dur"]), 2)
        agg.max_duration_ms   = round(float(values["max_dur"] or 0), 2)
        agg.min_duration_ms   = round(float(values["min_dur"] or 0), 2)
        agg.query_count       = int(values["cnt"] or 0)
        agg.total_rows        = int(values["rows"] or 0)
        agg.avg_memory_mb     = round(float(values["mem"] or 0), 2)
        agg.avg_cpu_pct       = round(float(values["cpu"] or 0), 2)
        agg.error_count       = int(values["err"] or 0)
        agg.save()
    return agg
