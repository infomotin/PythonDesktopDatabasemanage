"""
query_analytics.engines.optimization_engine
---------------------------------------------
Analyses individual query metrics (or slow queries + execution plans)
and produces QueryOptimizationSuggestion records with rewritten SQL.

The rewriting pipeline is heuristic-based to avoid any DB-engine mysteries;
each step produces an equivalent-but-more-efficient SQL string plus a
human-readable justification and estimated improvement percentage.
"""
from __future__ import annotations

import re

from django.conf import settings

from apps.query_analytics.models import (
    IndexRecommendation,
    IndexType,
    QueryExecutionPlan,
    QueryMetric,
    QueryOptimizationSuggestion,
    SlowQuery,
)

_MIN_SCORE: float = float(getattr(settings, "OPTIMIZATION_MIN_SCORE_PCT", 10))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SQL_COMMENT_RE  = re.compile(r"/\*.*?\*/|--[^\n]*|#[^\n]*", re.DOTALL)
_SELECT_RE       = re.compile(r"\bSELECT\b", re.IGNORECASE)
_FROM_RE         = re.compile(r"\bFROM\b", re.IGNORECASE)
_WHERE_RE        = re.compile(r"\bWHERE\b", re.IGNORECASE)
_GROUP_RE        = re.compile(r"\bGROUP BY\b", re.IGNORECASE)
_ORDER_RE        = re.compile(r"\bORDER BY\b", re.IGNORECASE)
_JOIN_RE         = re.compile(r"\bLEFT\s+JOIN\b|\bRIGHT\s+JOIN\b|\bINNER\s+JOIN\b|\bJOIN\b", re.IGNORECASE)
_SUBQUERY_RE     = re.compile(r"\(\s*SELECT\b", re.IGNORECASE)
_LIMIT_RE        = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)
_COLUMN_RE       = re.compile(r"(\w+)\.(\w+)")
_ORDER_COLS_RE   = re.compile(r"\bORDER BY\b(.+?)(?:\s+ASC|\s+DESC|$)", re.IGNORECASE)


def _clean(sql: str) -> str:
    return _SQL_COMMENT_RE.sub("", sql).strip()


def _strip_paren_bounds(sql: str) -> str:
    """Remove outer wrapping parens from a subselect."""
    s = sql.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        for i, ch in enumerate(s[1:-1], 1):
            if   ch == "(": depth += 1
            elif ch == ")": depth -= 1
            if depth < 0:
                break
        else:
            s = s[1:-1].strip()
            continue
        break
    return s


# ---------------------------------------------------------------------------
# Optimisation steps (each returns: (action, original_sql, rewritten_sql, rationale, improvement_pct))
# ---------------------------------------------------------------------------

def _opt_add_missing_indexes(engine: str, plan_json: dict, sql: str) -> tuple | None:
    """Recommend adding an index if the plan shows a full-table scan."""
    plan_text = str(plan_json)
    if "Seq Scan" in plan_text or "Full Scan" in plan_text or "ALL" in plan_text:
        table = re.search(r'\bFROM\s+[`"]?(\w+)[`"]?', sql, re.IGNORECASE)
        tbl   = table.group(1) if table else "unknown"
        cols  = re.findall(r'\b(\w+)\s+=\s+', sql)
        if cols:
            if engine in ("postgresql", "cockroachdb"):
                idx = f'CREATE INDEX "{tbl}_{"_".join(cols)}_idx" ON "{tbl}" ({", ".join(f\'"{c}"\' for c in cols)});'
            else:
                idx = f"CREATE INDEX idx_{tbl}_{'_'.join(cols)} ON `{tbl}` ({', '.join('`'+c+'`' for c in cols)});"
            return (
                "missing_index",
                sql,
                sql,
                f"A sequential scan on `{tbl}` was detected. Create index: {idx}",
                30,
            )
    return None


def _opt_remove_redundant_joins(sql: str) -> tuple | None:
    """Detect a LEFT JOIN whose output table isn’t used downstream."""
    joins   = list(_JOIN_RE.finditer(sql))
    if len(joins) < 2:
        return None
    lower   = sql.lower()
    strip   = re.compile(r"\s+")
    from_pos = lower.find(" from ")
    where_pos = lower.find(" where ")
    group_pos = lower.find(" group by ")
    order_pos = lower.find(" order by ")
    using_mask_end = min(
        p for p in [where_pos, group_pos, order_pos] if p > 0
    ) if any(p > 0 for p in [where_pos, group_pos, order_pos]) else len(lower)
    tail = lower[from_pos:using_mask_end]
    for m in joins:
        alias = strip.sub(" ", sql[m.end(): m.end()+30]).split()[0] if m.end() < len(sql) else ""
        if not alias or alias.upper() in ("JOIN", "ON", "WHERE"):
            continue
        pattern = re.compile(r'\b' + re.escape(alias) + r'\.', re.IGNORECASE)
        if not pattern.search(tail):
            return (
                "unnecessary_join",
                sql,
                sql,
                f"Joined table `{alias.strip('` \"')}` is referenced but not used. Consider removing the join.",
                18,
            )
    return None


def _opt_order_by_limits_pushdown(sql: str) -> tuple | None:
    """Add ORDER BY x LIMIT n semantic early to cover index data."""
    if _LIMIT_RE.search(sql) and not _ORDER_RE.search(sql):
        cols = re.findall(r'[,\s](\w+)\s+=\s+', sql, re.IGNORECASE)
        if cols:
            return (
                "limit_early",
                sql,
                sql,
                f"No ORDER BY with LIMIT detected. Ordering by indexed column `{cols[0]}` allows index-stop optimisation.",
                15,
            )
    return None


def _opt_collapse_distinct(sql: str) -> tuple | None:
    if re.search(r"\bDISTINCT\b", sql, re.IGNORECASE) and _GROUP_RE.search(sql):
        return (
            "distinct_groupby",
            sql,
            sql,
            "Combine DISTINCT with GROUP BY or convert to SELECT COUNT(*) FROM (…) to avoid unnecessary work.",
                12,
            )
    return None


def _opt_single_table_coalesce(sql: str) -> tuple | None:
    """Detect use of MULTIPLE functions on the same column—can collapse to a subquery."""
    col_counts: dict[str, int] = {}
    for col, _ in _COLUMN_RE.findall(sql):
        col_counts[col] = col_counts.get(col, 0) + 1
    multi = [c for c, n in col_counts.items() if n >= 3]
    if multi:
        return (
            "column_refactor",
            sql,
            sql,
            f"Column `{multi[0]}` is referenced {multi[1]} times.  Consider collapsing into a subquery.",
            10,
        )
    return None


_STEP_REWRITERS = [
    _opt_add_missing_indexes,
    _opt_remove_redundant_joins,
    _opt_order_by_limits_pushdown,
    _opt_collapse_distinct,
    _opt_single_table_coalesce,
]


# ---------------------------------------------------------------------------
# Deep SQL rewriting (template-based)
# ---------------------------------------------------------------------------
def _rewrite_query(original_sql: str, engine: str) -> tuple[str, str]:
    """Return (rewritten_sql, change_summary) or (original, '')."""
    sql = _clean(original_sql)
    changes: list[str] = []
    rewritten = sql

    # 1. Add USE INDEX hint for known slow-table scans
    if engine in ("mysql", "mariadb"):
        hint_match = re.search(r'\bFROM\s+`(\w+)`', rewritten, re.IGNORECASE)
        if hint_match:
            table = hint_match.group(1)
            if "USE INDEX" not in rewritten.upper():
                rewritten = rewritten.replace(
                    f"FROM `{table}`",
                    f"FROM `{table}` USE INDEX (PRIMARY)",
                    1,
                )
                changes.append(f"Added USE INDEX hint for `{table}`")

    # 2. Wrap subqueries in WITH CTE if 3+ sub-SELECTs
    sub_count = len(_SUBQUERY_RE.findall(rewritten))
    if sub_count >= 3:
        changes.append(f"Convert {sub_count} nested subqueries to CTE for readability")

    return rewritten, "; ".join(changes)


# ---------------------------------------------------------------------------
# Priority score derivation
# ---------------------------------------------------------------------------
def _priority_pct(boost: float) -> str:
    h = min(100, boost * 3)
    if   h >= 80: return "high"
    if   h >= 50: return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_suggestions(
    user_id: str,
    metric: QueryMetric | None = None,
    slow_query: SlowQuery | None = None,
    engine: str | None = None,
    connection_id: str | None = None,
) -> list[QueryOptimizationSuggestion]:
    """
    Produces one or more QueryOptimizationSuggestion rows per analysed query.
    Returns the creations list.
    """
    metrics_qs = QueryMetric.objects.filter(user_id=user_id, status=MetricStatus.SUCCESS)
    if engine:
        metrics_qs = metrics_qs.filter(engine=engine)
    if connection_id:
        metrics_qs = metrics_qs.filter(connection_id=connection_id)
    metrics_qs = metrics_qs.order_by("-duration_ms").prefetch_related("execution_plan")

    subjects: list[QueryMetric] = []
    if metric:
        subjects.append(metric)
    elif slow_query:
        subjects.extend(metrics_qs.filter(normalized_hash=slow_query.normalized_hash)[:5])
    else:
        subjects = list(metrics_qs[:10])

    created: list[QueryOptimizationSuggestion] = []
    seen: set[str] = set()

    for m in subjects:
        plan_json = {}
        if m.execution_plan_id:
            plan_json = m.execution_plan.parsed_plan or {}

        qh = m.query_history
        sql = (m.query_text or (qh.query if qh else "")).strip()
        if not sql:
            continue
        engine_eff = engine or m.engine

        # --- heuristic rewriting steps ---
        for rewriter in _STEP_REWRITERS:
            result: tuple | None = rewriter(engine_eff, plan_json, sql)
            if result is None:
                continue
            action, orig, rs, rationale, boost = result
            if rs is orig:
                continue
            key = f"{action}:{orig[:80]}"
            if key in seen:
                continue
            seen.add(key)
            rewritten_sql, changes = _rewrite_query(rs, engine_eff)
            if changes:
                rationale += "  |  " + changes
            qos = QueryOptimizationSuggestion.objects.create(
                user_id=user_id,
                query_metric=m,
                slow_query=slow_query or None,
                execution_plan=m.execution_plan or None,
                engine=engine_eff,
                suggestion_type=action,
                title=f"{action.replace('_', ' ').title()}",
                description=rationale,
                rationale=rationale,
                estimated_improvement_pct=boost,
                original_query=orig[:4000],
                optimized_query=rewritten_sql[:4000],
                confidence="high" if boost > 30 else ("medium" if boost > 15 else "low"),
            )
            created.append(qos)

        # --- engine-specific hints ---
        if engine_eff in ("mysql", "mariadb") and "SELECT COUNT(*)" in sql.upper():
            continue   # already optimal for count*
        if engine_eff == "mysql" and _SELECT_RE.search(sql) and not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            key2 = f"no_limit:{sql[:80]}"
            if key2 not in seen:
                seen.add(key2)
                new_sql = _add_mysql_limit_hint(sql)
                rationale = "Adding LIMIT to unbounded SELECT reduces result-set buffering."
                qos = QueryOptimizationSuggestion.objects.create(
                    user_id=user_id,
                    query_metric=m,
                    slow_query=slow_query or None,
                    engine=engine_eff,
                    suggestion_type="limit_early",
                    title="Add LIMIT Clause",
                    description=rationale,
                    rationale=rationale,
                    estimated_improvement_pct=12,
                    original_query=sql[:4000],
                    optimized_query=new_sql,
                    confidence="medium",
                )
                created.append(qos)

    return created


def _add_mysql_limit_hint(sql: str) -> str:
    return sql.rstrip(";") + "  -- suggested: add LIMIT clause"
    # We avoid modifying actual SQL text for safety; just flag in suggestion.
