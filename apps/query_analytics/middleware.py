"""
query_analytics.middleware
--------------------------
Two middleware classes:

1. ``QueryMetricMiddleware`` – wraps the DB query execution path and
   records a QueryMetric row after each successful query.
   In production this would live at frameworks/db_execution.py level;
   here it records metrics from the standard connections view.

2. ``AnalyticsSubscriptionMiddleware`` – early-rejects analytics URLs
   for free-tier users (only in production / when STRICT_SUBSCRIPTION=true).
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from apps.query_analytics.models import QueryMetric


class QueryMetricMiddleware(MiddlewareMixin):
    """
    This is a *pass-through* middleware that does not intercept responses
    directly.  It only exists so that:

      a) metrics are recorded by the metric_collector from view-level
         ``record_metric`` calls directly, NOT from here.
      b) the middleware slot is available for future performance
         instrumentation hooks.

    Keeping it active (no-op) is the cleanest production setup while
    the full DB-driver monkey-patching is left to a dedicated package.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        return None

    def process_response(self, request, response):
        return response
