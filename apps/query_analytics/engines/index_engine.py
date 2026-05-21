"""
query_analytics.engines.index_engine
--------------------------------------
Generates engine-specific index recommendations from slow-query history
and execution-plan analysis.

Supported engines: PostgreSQL, MySQL/MariaDB, Oracle, CockroachDB
"""
from __future__ import annotations

import re
from typing import List, Tuple

from django.conf import settings
from django.db.models import Avg

from apps.query_analytics.models import (
    IndexRecommendation,
    IndexType,
    MetricStatus,
    QueryExecutionPlan,
    QueryMetric,
    SlowQuery,
)
from apps.query_analytics.engines.plan_parser import parse

# ------------ configurable guardrails ---------------------------------
_RECOMMENDATION_THRESHOLD_PCT: float = float(
    getattr(settings, "RECOMMENDATION_IMPACT_PCT_THRESHOLD", 10)
)
_MIN_OCCURRENCES: int = int(getattr(settings, "RECOMMENDATION_MIN_OCCURRENCES", 3))
_MAX_RECS_PER_RUN: int = int(getattr(settings, "RECOMMENDATION_MAX_PER_RUN", 20))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_columns(sql: str) -> List[str]:
    """Extract column names appearing in WHERE, JOIN, ORDER BY, GROUP BY."""
    cols: List[str] = []
    for keyword in (r"where\s+", r"join\s+\w+\s+on\s+", r"group\s+by\s+", r"order\s+by\s+"):
        for match in re.finditer(keyword, sql, re.IGNORECASE):
            snippet = sql[match.end(): match.end() + 200]
            cols.extend(re.findall(r"(\w+)\s*(?:=|<>|!=|<|>|\s+and\s+|\s+or\s+|,|\s+by\s+)", snippet, re.IGNORECASE))
    return cols


def _table_name(sql: str) -> str | None:
    """Extract the primary table from a simple SELECT/UPDATE/DELETE."""
    m = re.search(
        r"\b(from|update|into)\s+([`\"]?\w+[`\"]?)",
        sql, re.IGNORECASE,
    )
    if m:
        return m.group(2).strip("`\"")
    return None


# ---------------------------------------------------------------------------
# Engine-specific DDL generators
# ---------------------------------------------------------------------------
_ENGINE_DDL_BUILDERS: dict[str, callable] = {}


def _mysql_ddl(table: str, cols: list[str], name: str | None = None) -> str:
    col_str = ", ".join(f"`{c}`" for c in cols)
    idx = name or f"idx_{table}_{'_'.join(cols)}"
    return f"CREATE INDEX `{idx}` ON `{table}` ({col_str});"


def _pg_ddl(table: str, cols: list[str], name: str | None = None) -> str:
    import re as _re
    col_str = ", ".join(f'"{c}"' for c in cols)
    idx = name or f"idx_{table}_{'_'.join(cols)}"
    return f'CREATE INDEX "{idx}" ON "{table}" ({col_str});'


def _oracle_ddl(table: str, cols: list[str], name: str | None = None) -> str:
    col_str = ", ".join(f'"{c}"' for c in cols)
    return f"CREATE INDEX {name or 'IDX_TMP'} ON \"{table}\" ({col_str});"


def _pg_gist_cols(cols: list[str]) -> str:
    return ", ".join(f'"{c}"' for c in cols)


def _pg_gin_cols(cols: list[str]) -> str:
    return ", ".join(f'"{c}"' for c in cols)


# Engine defaults
def _default_engine_index_type(engine: str, cols: List[str]) -> Tuple[str, IndexType, str]:
    if engine in ("postgresql", "cockroachdb"):
        return ("btree", IndexType.BTREE, _pg_ddl)
    if engine == "oracle":
        return ("btree", IndexType.BTREE, _oracle_ddl)
    if engine == "mongodb":
        return ("btree", IndexType.BTREE, lambda t, c, n: f"db.{t}.createIndex({list(c)})")
    return ("btree", IndexType.BTREE, _mysql_ddl)


def _engine_index_type(engine: str, cols: List[str]) -> Tuple[str, IndexType]:
    """Return (index_name, IndexType enum) for the engine."""
    sql_tail = " ".join(cols).lower()
    if engine in ("postgresql", "cockroachdb"):
        if any(k in sql_tail for k in ("json", "array", "tsvector", "fulltext", "tsquery")):
            return ("gin", IndexType.GIN)
        if any(k in sql_tail for k in ("geometry", "geography", "point", "polygon")):
            return ("gist", IndexType.GIST)
        return ("btree", IndexType.BTREE)
    if engine in ("mysql", "mariadb"):
        return ("btree", IndexType.BTREE)
    if engine == "oracle":
        return ("btree", IndexType.BTREE)
    if engine == "mongodb":
        return ("btree", IndexType.BTREE)
    return ("btree", IndexType.BTREE)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _score(metric: QueryMetric) -> float:
    """0–100 score based on duration, occurrence rate, and memory/CPU cost."""
    dur = metric.duration_ms
    if dur < 100:
        return 0.0
    base = min(100, (dur / 5000) * 80)
    if metric.memory_consumed_mb > 256:
        base += 10
    if metric.cpu_percent > 80:
        base += 10
    return min(100.0, base)


def _estimated_improvement_pct(score: float) -> float:
    return round(score * 0.8, 1)


def _rationale(table: str, cols: List[str], engine: str, score: float) -> str:
    col_str = ", ".join(cols)
    engine_name = engine.replace("_", " ").title()
    return (
        f"The execution plan for queries against `{table}` frequently performs "
        f"full-table scans on {engine_name}. A composite index on "
        f"`{col_str}` would allow the engine to seek directly to matching rows. "
        f"Projected improvement: ~{score:.0f}%."
    )


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def generate_recommendations(
    user_id: str,
    engine: str | None = None,
    connection_id: str | None = None,
) -> List[IndexRecommendation]:
    """
    Runs the index-recommendation pipeline for *user_id*, optionally
    scoped to a single *engine* and/or *connection_id*.
    Returns a list of **newly created** IndexRecommendation objects.
    """
    qs = SlowQuery.objects.filter(user_id=user_id)
    if engine:
        qs = qs.filter(engine=engine)
    if connection_id:
        qs = qs.filter(connection_id=connection_id)

    # Each slow query must have appeared at least _MIN_OCCURRENCES times
    qs = qs.filter(occurrence_count__gte=_MIN_OCCURRENCES).prefetch_related("metrics")

    if not qs.exists():
        return []

    from apps.connections.models import DatabaseConnection
    conn_map = {
        str(c.id): c
        for c in DatabaseConnection.objects.filter(user_id=user_id)
    }

    created: List[IndexRecommendation] = []
    seen: set[tuple] = set()

    for sq in qs[: _MAX_RECS_PER_RUN]:
        conn = conn_map.get(str(sq.connection_id)) if sq.connection_id else None
        table = _table_name(sq.query_text)
        if not table:
            continue

        cols = _extract_columns(sq.query_text)
        if not cols:
            continue

        engine_eff = engine or sq.engine
        idx_name, idx_type = _engine_index_type(engine_eff, cols)
        safe_table = table.replace('"', '')
        safe_cols   = [c.replace('"', '') for c in cols]
        cols_key = "_".join(safe_cols)
        dedup_key = (engine_eff, safe_table, cols_key, idx_name)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        ddl_fn = {
            "mysql": _mysql_ddl,
            "mariadb": _mysql_ddl,
            "postgresql": _pg_ddl,
            "cockroachdb": _pg_ddl,
            "oracle": _oracle_ddl,
        }.get(engine_eff, _mysql_ddl)

        statement = ddl_fn(safe_table, safe_cols, f"idx_{safe_table}_{cols_key}")

        avg_dur  = sq.avg_duration_ms
        score    = min(100.0, max(0.0, avg_dur * 0.8))
        est_pct  = _estimated_improvement_pct(score)

        rec = IndexRecommendation.objects.create(
            user_id=user_id,
            connection=conn,
            engine=engine_eff,
            table_name=safe_table,
            column_names=safe_cols,
            index_type=idx_type,
            index_name_suggestion=f"idx_{safe_table}_{cols_key}",
            create_statement=statement,
            score=score,
            estimated_improvement_pct=est_pct,
            rationale=_rationale(safe_table, safe_cols, engine_eff, score),
            threshold_ms=float(getattr(settings, "SLOW_QUERY_THRESHOLD_MS", 500)),
        )
        rec.slow_queries.add(sq)
        created.append(rec)

    return created
