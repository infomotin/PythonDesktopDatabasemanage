"""
query_analytics.engines.alert_engine
--------------------------------------
Runs a series of resource-threshold rules against a newly-arrived QueryMetric
and, when a rule fires, emits a PerformanceAlert (and optionally a notification).
"""

import datetime as _dt
from typing import Optional

from django.conf import settings
from django.db.models import Max, F

from apps.query_analytics.models import (
    ConnectionSnapshot,
    MetricAggregate,
    MetricStatus,
    PerformanceAlert,
    QueryMetric,
)

# ---------------------------------------------------------------------------
# Thresholds (override via environment variables)
# ---------------------------------------------------------------------------
_CPU_THRESHOLD_PCT:   float = float(getattr(settings, "ALERT_CPU_THRESHOLD_PCT",         85))
_MEM_THRESHOLD_MB:    float = float(getattr(settings, "ALERT_MEM_THRESHOLD_MB",          512))
_DURATION_CRITICAL_MS:float = float(getattr(settings, "ALERT_DURATION_CRITICAL_MS",     3000))
_DURATION_WARNING_MS: float = float(getattr(settings, "ALERT_DURATION_WARNING_MS",       500))
_POOL_SATURATION_PCT: float = float(getattr(settings, "ALERT_POOL_SATURATION_PCT",       90))
_RATE_LIMIT_SECONDS:  float = float(getattr(settings, "ALERT_RATE_LIMIT_SECONDS",        60))


def _rate_limited(user_id: str, alert_type: str) -> bool:
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=_RATE_LIMIT_SECONDS)
    return PerformanceAlert.objects.filter(
        user_id=user_id, alert_type=alert_type, created_at__gte=cutoff,
    ).exists()


# ---------------------------------------------------------------------------
# Individual rule functions
# ---------------------------------------------------------------------------
def _check_cpu_spike(metric: QueryMetric) -> Optional[PerformanceAlert]:
    if metric.cpu_percent < _CPU_THRESHOLD_PCT:
        return None
    if _rate_limited(str(metric.user_id), "cpu_spike"):
        return None
    return PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="cpu_spike",
        priority=PerformanceAlert.AlertPriority.MEDIUM,
        title=f"High CPU usage — {metric.engine}",
        message=(
            f"Query consumed {metric.cpu_percent:.1f}% CPU "
            f"({metric.duration_ms:.1f} ms execution time, "
            f"{metric.memory_consumed_mb:.1f} MB memory)."
        ),
        metric_snapshot={
            "cpu_percent": metric.cpu_percent,
            "duration_ms": metric.duration_ms,
            "engine": metric.engine,
        },
    )


def _check_memory(metric: QueryMetric) -> Optional[PerformanceAlert]:
    if metric.memory_consumed_mb < _MEM_THRESHOLD_MB:
        return None
    if _rate_limited(str(metric.user_id), "memory_pressure"):
        return None
    return PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="memory_pressure",
        priority=PerformanceAlert.AlertPriority.HIGH,
        title=f"Memory pressure — {metric.engine}",
        message=(
            f"Query consumed {metric.memory_consumed_mb:.1f} MB "
            f"(threshold {_MEM_THRESHOLD_MB} MB). "
            f"Duration: {metric.duration_ms:.1f} ms."
        ),
        metric_snapshot={"memory_mb": metric.memory_consumed_mb, "duration_ms": metric.duration_ms},
    )


def _check_critical_duration(metric: QueryMetric) -> Optional[PerformanceAlert]:
    if metric.duration_ms < _DURATION_CRITICAL_MS:
        return None
    if _rate_limited(str(metric.user_id), "duration_critical"):
        return None
    return PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="duration_critical",
        priority=PerformanceAlert.AlertPriority.CRITICAL,
        title=f"Critical query duration — {metric.duration_ms:.0f} ms",
        message=(
            f"A query on {metric.engine} ran {metric.duration_ms:.0f} ms, "
            f"exceeding the critical threshold of {_DURATION_CRITICAL_MS} ms.\n"
            f"Query: {metric.query_text[:300]}"
        ),
        metric_snapshot={"duration_ms": metric.duration_ms, "engine": metric.engine, "status": metric.status},
    )


def _check_pool_saturation(metric: QueryMetric) -> Optional[PerformanceAlert]:
    if not metric.connection_id:
        return None
    latest = (
        ConnectionSnapshot.objects.filter(connection_id=metric.connection_id)
        .order_by("-timestamp")
        .first()
    )
    if not latest or latest.usage_pct() < _POOL_SATURATION_PCT:
        return None
    if _rate_limited(str(metric.user_id), "pool_saturation"):
        return None
    return PerformanceAlert.objects.create(
        user=metric.user,
        connection=metric.connection,
        alert_type="pool_saturation",
        priority=PerformanceAlert.AlertPriority.HIGH,
        title=f"Connection pool saturated — {metric.connection.name}",
        message=(
            f"{latest.total_connections}/{latest.max_capacity} connections in use "
            f"({latest.usage_pct():.0f}%)."
        ),
        metric_snapshot={"usage_pct": latest.usage_pct(), "total": latest.total_connections, "max": latest.max_capacity},
    )


_RULES: list = [_check_cpu_spike, _check_memory, _check_critical_duration, _check_pool_saturation]


def check_bottlenecks(metric: QueryMetric) -> None:
    """Iterate all rules and fire alerts where conditions are met."""
    for rule in _RULES:
        try:
            rule(metric)
        except Exception:
            pass
