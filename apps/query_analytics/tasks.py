"""Background tasks: periodic resource snapshots, stale-index sweep."""

import time

from django.db import models
from django.utils import timezone

from apps.connections.models import DatabaseConnection
from apps.query_analytics.models import ResourceSnapshot, QueryPlanCache
from apps.query_analytics.services.metric_collector import _take_resource_snapshot


def take_all_resource_snapshots():
    """Called by Celery beat — snapshots every active connection."""
    for conn in DatabaseConnection.objects.filter(is_active=True).only("id", "user_id"):
        user = conn.user
        try:
            _take_resource_snapshot(user, conn, conn.engine)
        except Exception:
            pass


def purge_stale_plans(days: int = 30):
    """Remove plan-cache entries not accessed in `days` days."""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    QueryPlanCache.objects.filter(last_used_at__lt=cutoff).delete()
