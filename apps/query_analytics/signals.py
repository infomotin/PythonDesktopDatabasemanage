"""
query_analytics.signals
----------------------
Registers signal handlers so that whenever a QueryMetric is saved the
slow-query tracker and the real-time broadcast channel are notified.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import QueryMetric, SlowQuery


@receiver(post_save, sender=QueryMetric)
def on_metric_saved(sender, instance, created, **kwargs):
    from .engines.slow_query_engine import SlowQueryEngine
    from .engines.alert_engine import AlertEngine

    if not created:
        return

    SlowQueryEngine.check_threshold(instance)
    AlertEngine.check_bottlenecks(instance)


@receiver(post_delete, sender=SlowQuery)
def _cleanup_slow_query_data(sender, instance, **kwargs):
    pass  # placeholder – could trigger related-recommendation expiry
