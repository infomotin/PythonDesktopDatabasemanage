"""
query_analytics.signals
----------------------
Registers signal handlers so that whenever a QueryHistory or QueryMetric
is saved the relevant analytics subsystem is notified.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.db_query_history.models import QueryHistory
from apps.query_analytics.models import QueryMetric


@receiver(post_save, sender=QueryHistory)
def on_query_history_saved(sender, instance, created, **kwargs):
    """
    Persist a QueryMetric row for every successful/failed query recorded
    in db_query_history.  The QueryHistory model already stores duration_ms
    and affected_rows so we can mirror those into the metric store.
    """
    try:
        from apps.query_analytics.engines.metric_collector import record_metric
        record_metric(
            user=instance.user,
            engine=instance.database.engine if instance.database else "unknown",
            query_text=instance.query[:4000],
            duration_ms=instance.execution_time or 0,
            rows_affected=instance.affected_rows,
            connection=instance.connection,
            query_history=instance,
            success=instance.success,
            error_message=instance.error_message or "",
            status="error" if not instance.success else "success",
            memory_mb=0,
            cpu_pct=0,
        )
    except Exception:
        pass  # never block a query on analytics


@receiver(post_save, sender=QueryMetric)
def on_metric_saved(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from apps.query_analytics.engines.slow_query_engine import check_threshold
        check_threshold(instance)
    except Exception:
        pass
    try:
        from apps.query_analytics.engines.alert_engine import check_bottlenecks
        check_bottlenecks(instance)
    except Exception:
        pass
