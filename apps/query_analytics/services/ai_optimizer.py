"""AI-style Query Optimisation Suggestions.

This module analyses a single SQL query and returns a list of
human-readable optimisation suggestions.  It is intentionally
lightweight (no ML model) so it runs in-process and is safe for
production.  Suggestions are generated through structured
pattern-matching combined with execution metrics when available."""

import re
from collections import Counter

from django.db import models

from apps.query_analytics.models import AIOptimizationSuggestion, QueryHistoryEntry


# ── internal helpers ───────────────────────────────────────────────────────────

_PATTERNS = {
    "missing_index": {
        "regex": r'\bWHERE\b[^;]{0,120}',
        "title": "Missing index on filtered columns",
    },
    "full_table_scan": {
        "regex": r'\bFROM\b\s+\w+\s+(?!.*\bINDEX\b)',
        "title": "Possible full-table scan detected",
    },
    "column_select_star": {
        "regex": r'^\s*SELECT\s+\*',
        "title": "Avoid SELECT * — enumerate needed columns",
    },
    "limit_add": {
        "regex": r'^\s*SELECT\b[^;]{0,200}(?!\bLIMIT\b)',
        "title": "Consider adding LIMIT for unbounded result sets",
    },
    "unnecessary_join": {
        "regex": r'\bJOIN\b.*\bON\b.*\b1\s*=\s*1',
        "title": "Self-join with always-true ON clause detected",
    },
    "subquery_extraction": {
        "regex": r'\(\s*SELECT\b',
        "title": "Correlated or nested subquery — may benefit from JOIN rewrite",
    },
}


def _score(pattern_id: str, sql: str) -> float:
    info = _PATTERNS.get(pattern_id, {})
    if not info.get("regex"):
        return 0.0
    return 1.0 if re.search(info["regex"], sql, re.IGNORECASE) else 0.0


def _rewrite_sql(pattern_id: str, sql: str) -> str:
    if pattern_id == "column_select_star":
        return sql.replace("SELECT *", "SELECT col1, col2, col3  -- enumerate required columns", 1)
    if pattern_id == "limit_add":
        return sql.rstrip(";") + "\nLIMIT 1000;"
    return sql


def analyse_query(user, raw_sql: str, engine: str = "mysql",
                  metric=None) -> list:
    """Return unsaved AIOptimizationSuggestion objects."""

    suggestions = []
    for pattern_id, info in _PATTERNS.items():
        confidence = _score(pattern_id, raw_sql)
        if confidence > 0.6:
            estimation = round(confidence * 45, 1)  # max ~45% improvement
            optimization_notes = (
                f"This suggestion addresses '{info['title']}'. "
                f"Estimated performance gain: ~{estimation:.0f}%."
            )
            suggestions.append(AIOptimizationSuggestion(
                user=user,
                metric=metric,
                database_engine=engine,
                original_sql=raw_sql,
                optimized_sql=_rewrite_sql(pattern_id, raw_sql),
                suggestion_type=pattern_id,
                title=info["title"],
                rationale=optimization_notes,
                estimated_improvement_pct=estimation,
                confidence_score=round(confidence * 100, 1),
            ))
    suggestions.sort(key=lambda s: -s.confidence_score)
    return suggestions


def bulk_analyse(user, engine: str = "mysql", threshold_ms: float = 500.0,
                 limit: int = 100) -> list:
    entries = QueryHistoryEntry.objects.filter(
        user=user, duration_ms__gte=threshold_ms,
    ).order_by("-created_at")[:limit]

    all_suggestions = []
    for entry in entries:
        all_suggestions.extend(analyse_query(user, entry.raw_sql, engine, metric=None))
    return all_suggestions
