"""Query replay & cross-engine comparison engine."""

import time
from collections import namedtuple

from django.utils import timezone

from apps.connections.utils import ConnectionPool
from apps.core.crypto import decrypt_credential
from apps.connections.models import DatabaseConnection
from apps.query_analytics.models import (
    QueryReplayRecord, PerformanceComparison, QueryExecutionMetric,
)
from apps.query_analytics.services.metric_collector import collect_metrics


ReplayResult = namedtuple("ReplayResult", ["duration_ms", "rows_returned", "rows_affected",
                                            "memory_mb", "status", "error", "result_columns"])


def replay_query(
    user,
    metric: QueryExecutionMetric,
    modified_params: dict = None,
    connection: DatabaseConnection = None,
) -> QueryReplayRecord:
    """Re-execute a previously captured query and persist a ReplayRecord."""
    from django.db import models
    conn = connection or metric.connection
    pwd = decrypt_credential(conn.password) if conn else None

    sql = metric.raw_sql
    params = modified_params or metric.params
    alias = ConnectionPool.get(conn) if conn else None
    start = time.perf_counter()
    rows_returned = 0
    rows_affected = 0
    status = "success"
    error_msg = None
    result_columns = []

    try:
        with models.connections[alias].cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                result_columns = [c[0] for c in cur.description]
                rows = [list(r) for r in cur.fetchall()]
                rows_returned = len(rows)
            else:
                rows_affected = cur.rowcount
    except Exception as exc:
        status = "error"
        error_msg = str(exc)
    elapsed_ms = (time.perf_counter() - start) * 1000

    record = QueryReplayRecord.objects.create(
        original=metric,
        user=user,
        duration_ms=round(elapsed_ms, 3),
        rows_affected=rows_affected,
        rows_returned=rows_returned,
        status=status,
        error_message=error_msg or "",
        modified_params=params if modified_params else {},
    )
    return record


def compare_engines(
    user,
    logical_sql: str,
    engine_a: str,
    engine_b: str,
    connection_a: DatabaseConnection = None,
    connection_b: DatabaseConnection = None,
) -> PerformanceComparison:
    """Execute the same logical query on two engines and compare the results."""

    def _run(engine_key, conn):
        if conn:
            result = collect_metrics(user, conn, logical_sql)
            return (result["duration_ms"], result["rows_affected"], result["memory_mb"], result.get("execution_plan", {}))
        try:
            from apps.core.adapters.factory import EngineFactory
            adapter = EngineFactory.create(
                engine_key, host="localhost", port=conn.port if conn else 3306,
                dbname=conn.dbname if conn else "test",
                username=conn.username if conn else "", password="",
            )
            return adapter.execute(logical_sql) if adapter else (0, 0, 0, {})
        except Exception as exc:
            return (0, 0, 0, {"error": str(exc)})

    dur_a, rows_a, mem_a, plan_a = _run(engine_a, connection_a)
    dur_b, rows_b, mem_b, plan_b = _run(engine_b, connection_b)

    delta_pct = round((dur_a - dur_b) / max(dur_a, dur_b) * 100, 1) if max(dur_a, dur_b) > 0 else 0

    return PerformanceComparison.objects.create(
        user=user,
        name=f"{engine_a} vs {engine_b}",
        logical_sql=logical_sql,
        engine_a=engine_a,
        engine_b=engine_b,
        duration_a_ms=dur_a,
        rows_a=rows_a,
        memory_a_mb=mem_a,
        plan_a=plan_a,
        duration_b_ms=dur_b,
        rows_b=rows_b,
        memory_b_mb=mem_b,
        plan_b=plan_b,
        winner=engine_a if dur_a < dur_b else engine_b,
        delta_pct=abs(delta_pct),
    )
