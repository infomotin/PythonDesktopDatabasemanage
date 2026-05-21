"""Metrics collector — wraps a SQL execution, captures timing, memory, CPU, plan."""

import time
import tracemalloc
import traceback

from django.db import models
from django.utils import timezone

from apps.core.crypto import decrypt_credential
from apps.connections.utils import ConnectionPool
from apps.query_analytics.models import (
    QueryExecutionMetric, QueryHistoryEntry, QueryPlanCache,
    SlowQueryAlert, ResourceSnapshot, QueryPattern,
)


# ── engine-native EXPLAIN map ──────────────────────────────────────────────────

EXPLAIN_MAP = {
    "mysql": "EXPLAIN ANALYZE",
    "postgresql": "EXPLAIN (ANALYZE, BUFFERS)",
    "mariadb": "EXPLAIN ANALYZE",
    "cockroachdb": "EXPLAIN (ANALYZE, BUFFERS)",
    "sqlserver": "SET SHOWPLAN_XML ON",
    "oracle": "EXPLAIN PLAN FOR",
}


def _engine_plan_prefix(engine: str) -> str:
    return EXPLAIN_MAP.get(engine.lower(), "EXPLAIN")


def _capture_plan(alias: str, sql: str) -> dict:
    """Run EXPLAIN and return a structured plan dict."""
    plan_sql = f"{_engine_plan_prefix(alias.split('_')[0] if '_' in alias else '')} {sql}"
    try:
        with models.connections[alias].cursor() as cur:
            cur.execute(plan_sql)
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        return {"columns": cols, "rows": rows[:200]}
    except Exception:
        return {"error": traceback.format_exc()}


def _detect_query_type(sql: str) -> str:
    s = sql.strip().upper()
    for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "EXEC"):
        if s.startswith(kw):
            return kw.lower()
        if kw == "EXEC" and s.startswith("EXECUTE"):
            return "exec"
    return "other"


def _update_query_pattern(metric: QueryExecutionMetric) -> None:
    fp = metric.query_fingerprint
    pattern, created = QueryPattern.objects.get_or_create(
        fingerprint=fp,
        user=metric.user,
        defaults={
            "connection": metric.connection,
            "engine": metric.database_engine,
            "sample_sql": metric.raw_sql,
            "query_type": metric.query_type,
        },
    )
    if not created:
        pattern.total_executions = models.F("total_executions") + 1
        pattern.avg_duration_ms = (pattern.avg_duration_ms * (pattern.total_executions - 1) + metric.duration_ms) / pattern.total_executions
        if metric.duration_ms < pattern.min_duration_ms:
            pattern.min_duration_ms = metric.duration_ms
        if metric.duration_ms > pattern.max_duration_ms:
            pattern.max_duration_ms = metric.duration_ms
        pattern.last_executed_at = metric.created_at
        pattern.save(update_fields=["total_executions", "avg_duration_ms", "min_duration_ms", "max_duration_ms", "last_executed_at"])


def _check_slow_alert(metric: QueryExecutionMetric, threshold_ms: float = 500.0) -> None:
    if metric.duration_ms >= threshold_ms:
        SlowQueryAlert.objects.create(
            user=metric.user,
            metric=metric,
            threshold_ms=threshold_ms,
            message=f"Slow query: {metric.query_type.upper()} took {metric.duration_ms:.1f}ms on {metric.database_engine}/{metric.connection.dbname if metric.connection else 'N/A'}",
        )


# ── public API ─────────────────────────────────────────────────────────────────

def collect_metrics(
    user,
    connection: "apps.connections.models.DatabaseConnection",
    raw_sql: str,
    params=None,
    *,
    threshold_ms: float = 500.0,
    take_snapshot: bool = True,
    history_retention_days: int = 90,
) -> dict:
    """Execute a SQL query, capture all metrics, and persist them."""
    if params is None:
        params = {}

    alias = ConnectionPool.get(connection) if connection else None
    engine = getattr(connection, "engine", "sqlite") if connection else "sqlite"
    db = getattr(connection, "dbname", "") if connection else ""
    query_type = _detect_query_type(raw_sql)
    params_serialised = params if isinstance(params, dict) else {}

    result_columns, result_rows = [], []
    rows_affected = 0
    rows_returned = 0
    status = "success"
    error_msg = None
    plan = {}
    memory_delta_mb = 0
    cpu_ms_val = 0

    tracemalloc.start()
    start = time.perf_counter()
    try:
        with models.connections[alias].cursor() as cursor:
            cursor.execute(raw_sql, params_serialised)
            if cursor.description:
                result_columns = [c[0] for c in cursor.description]
                result_rows = [list(r) for r in cursor.fetchall()]
                rows_returned = len(result_rows)
            else:
                rows_affected = cursor.rowcount
    except Exception as exc:
        status = "error"
        error_msg = str(exc)
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _, mem_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        memory_delta_mb = mem_peak / 1024 / 1024
        plan = _capture_plan(alias, raw_sql) if alias else {}

    metric = QueryExecutionMetric.objects.create(
        user=user,
        connection=connection,
        raw_sql=raw_sql,
        query_fingerprint="",
        params=params_serialised,
        duration_ms=round(elapsed_ms, 3),
        rows_affected=rows_affected,
        rows_returned=rows_returned,
        memory_mb=round(memory_delta_mb, 3),
        cpu_ms=round(cpu_ms_val, 3),
        status=status,
        error_message=error_msg or "",
        execution_plan=plan,
        query_type=query_type,
        database_engine=engine,
    )

    QueryHistoryEntry.objects.create(
        user=user,
        connection=connection,
        raw_sql=raw_sql,
        query_fingerprint=metric.query_fingerprint,
        query_type=query_type,
        params=params_serialised,
        duration_ms=metric.duration_ms,
        rows_affected=rows_affected,
        result_columns=result_columns,
        result_preview=result_rows[:100],
        result_row_count=rows_returned,
        success=(status == "success"),
        error_message=error_msg or "",
        execution_plan=plan,
    )

    if take_snapshot:
        _update_query_pattern(metric)
        _check_slow_alert(metric, threshold_ms)
        _take_resource_snapshot(user, connection, engine)

    return {
        "metric_id": str(metric.id),
        "duration_ms": metric.duration_ms,
        "rows_affected": rows_affected,
        "rows_returned": rows_returned,
        "memory_mb": metric.memory_mb,
        "status": status,
        "error": error_msg,
        "execution_plan": plan,
    }


def _take_resource_snapshot(user, connection, engine: str):
    """Take a resource snapshot for the given connection."""
    try:
        active = 0
        idle = 0
        pool_usage = 0
        try:
            from django.db import connections as dj_conns
            active = sum(1 for c in dj_conns.all() if getattr(c, "connection", None) is not None)
        except Exception:
            pass
        ResourceSnapshot.objects.create(
            user=user,
            connection=connection,
            active_connections=active,
            idle_connections=idle,
            pool_capacity=active + idle,
            pool_usage_pct=pool_usage,
            has_bottleneck=(pool_usage > 90),
        )
    except Exception:
        pass
