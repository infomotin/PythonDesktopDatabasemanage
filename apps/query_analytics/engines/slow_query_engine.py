"""
query_analytics.engines.slow_query_engine
------------------------------------------
Detects slow queries, bucketing duplicate normalised queries into SlowQuery
records and updating their statistics when a new crossing-query appears.
"""
from __future__ import annotations

import timezone

from django.conf import settings

from apps.query_analytics.models import QueryMetric, SlowQuery


# Configurable threshold (ms).  Override via env: SLOW_QUERY_THRESHOLD_MS=500
_THRESHOLD_MS: float = int(getattr(settings, "SLOW_QUERY_THRESHOLD_MS", 500))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def check_threshold(metric: QueryMetric) -> SlowQuery | None:
    """If *metric* is slow, create or update the corresponding SlowQuery."""
    if metric.duration_ms < _THRESHOLD_MS:
        return None

    sq, created = SlowQuery.objects.get_or_create(
        normalized_hash=metric.normalized_hash,
        user=metric.user,
        engine=metric.engine,
        defaults=dict(
            connection=metric.connection,
            query_text=metric.query_text,
            query_type=metric.query_type,
            avg_duration_ms=metric.duration_ms,
            max_duration_ms=metric.duration_ms,
            occurrence_count=1,
            first_seen=metric.executed_at,
            last_seen=metric.executed_at,
            threshold_ms=_THRESHOLD_MS,
        ),
    )
    if not created:
        sq.increment(metric.duration_ms)

    # Mark the metric so dashboards can colour it
    metric.is_slow = True
    metric.save(update_fields=["is_slow"])
    return sq
