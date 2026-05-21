"""
query_analytics.engines.alert_engine
--------------------------------------
Runs a series of resource-threshold rules against a newly-arrived QueryMetric
and, when a rule fires, emits a PerformanceAlert (and optionally a notification).
"""

from django.conf import settings
from django.db.models import Avg, F

from apps.query_analytics.models import (
    ConnectionSnapshot,
    MetricAggregate,
    MetricStatus,
    PerformanceAlert,
    QueryMetric,
)
from apps.query_analytics.engines import plan_parser

# ---------------------------------------------------------------------------
# Thresholds (override via env, values in milliseconds unless noted)
# ---------------------------------------------------------------------------
_CPU_THRESHOLD_PCT: float = float(getattr(settings, "ALERT_CPU_THRESHOLD_PCT", 85))
_MEM_THRESHOLD_MB: float  = float(getattr(settings, "ALERT_MEM_THRESHOLD_MB", 512))
_DURATION_CRITICAL_MS: float = float(getattr(settings, "ALERT_DURATION_CRITICAL_MS", 3000))
_DURATION_WARNING_MS: float  = float(getattr(settings, "ALERT_DURATION_WARNING_MS",  500))
_POOL_SATURATION_PCT: float  = float(getattr(settings, "ALERT_POOL_SATURATION_PCT", 90))
_RATE_LIMIT_SECONDS: float   = float(getattr(settings, "ALERT_RATE_LIMIT_SECONDS", 60))
import datetime as _dt


def _rate_limited(user_id, alert_type: str) -> bool:
    """Return True if an alert of *alert_type* was already sent to *user_id*
    within the past RATE_LIMIT_SECONDS so we don’t spam."""
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(
        seconds=_RATE_LIMIT_SECONDS
    )
    existing = PerformanceAlert.objects.filter(
        user_id=user_id, alert_type=alert_type, created_at__gte=cutoff
    )
    return existing.exists()


# ---------------------------------------------------------------------------
# Rule: CPU spike
# ---------------------------------------------------------------------------
def _check_cpu_spike(metric: QueryMetric) -> PerformanceAlert | None:
    if metric.cpu_percent < _CPU_THRESHOLD_PCT:
        return None
    if _rate_limited(metric.user_id, "cpu_spike"):
        return None
    alert = PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="cpu_spike",
        priority=PerformanceAlert.AlertPriority.MEDIUM,
        title=f"High CPU usage detected — {metric.engine}",
        message=(
            f"Query '{metric.query_text[:80]}' is consuming "
            f"{metric.cpu_percent:.1f}% CPU on {metric.get_engine_display() if hasattr(metric, 'get_engine_display') else metric.engine}."
        ),
        metric_snapshot={
            "cpu_percent": metric.cpu_percent,
            "duration_ms": metric.duration_ms,
            "engine": metric.engine,
        },
    )
    return alert


# ---------------------------------------------------------------------------
# Rule: Memory pressure
# ---------------------------------------------------------------------------
def _check_memory(metric: QueryMetric) -> PerformanceAlert | None:
    if metric.memory_consumed_mb < _MEM_THRESHOLD_MB:
        return None
    if _rate_limited(metric.user_id, "memory_pressure"):
        return None
    alert = PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="memory_pressure",
        priority=PerformanceAlert.AlertPriority.HIGH,
        title=f"Memory pressure — {metric.engine}",
        message=(
            f"Query consumed {metric.memory_consumed_mb:.1f} MB memory "
            f"(threshold: {_MEM_THRESHOLD_MB} MB)."
        ),
        metric_snapshot={
            "memory_mb": metric.memory_consumed_mb,
            "duration_ms": metric.duration_ms,
        },
    )
    return alert


# ---------------------------------------------------------------------------
# Rule: Critical duration
# ---------------------------------------------------------------------------
def _check_critical_duration(metric: QueryMetric) -> PerformanceAlert | None:
    if metric.duration_ms < _DURATION_CRITICAL_MS:
        return None
    if _rate_limited(metric.user_id, "duration_critical"):
        return None
    alert = PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="duration_critical",
        priority=PerformanceAlert.AlertPriority.CRITICAL,
        title=f"Critical query duration — {metric.duration_ms:.0f} ms",
        message=(
            f"A query on {metric.engine} ran {metric.duration_ms:.0f} ms, "
            f"exceeding the critical threshold of {_DURATION_CRITICAL_MS} ms."
            f"\nQuery: {metric.query_text[:200]}"
        ),
        metric_snapshot={
            "duration_ms": metric.duration_ms,
            "engine": metric.engine,
            "status": metric.status,
        },
    )
    return alert


# ---------------------------------------------------------------------------
# Rule: Connection-pool saturation
# ---------------------------------------------------------------------------
def _check_pool_saturation(metric: QueryMetric) -> PerformanceAlert | None:
    if not metric.connection_id:
        return None
    latest_snapshot = (
        ConnectionSnapshot.objects.filter(connection_id=metric.connection_id)
        .order_by("-timestamp")
        .first()
    )
    if not latest_snapshot:
        return None
    if latest_snapshot.usage_pct() < _POOL_SATURATION_PCT:
        return None
    if _rate_limited(metric.user_id, "pool_saturation"):
        return None
    PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="pool_saturation",
        priority=PerformanceAlert.AlertPriority.HIGH,
        title=f"Connection pool saturated — {metric.connection.name}",
        message=(
            f"{latest_snapshot.total_connections}/{latest_snapshot.max_capacity} "
            f"connections in use ({latest_snapshot.usage_pct():.0f}%)."
        ),
        metric_snapshot=latest_snapshot.usage_pct(),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
_RULES = [_check_cpu_spike, _check_memory, _check_critical_duration, _check_pool_saturation]


def check_bottlenecks(metric: QueryMetric) -> None:
    """Iterate all规则 and fire alerts where conditions are met."""
    for rule in _RULES:
        try:
            rule(metric)
        except Exception:
            pass
