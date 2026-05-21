"""
query_analytics.management.commands.run_analytics
-------------------------------------------------
Management command:
  python manage.py run_analytics [--type slow|opt|alerts|all] [--user <uuid>]

Runs one or all analytics pipelines on-demand.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.apps import apps

Model = apps.get_model
SlowQ       = Model("query_analytics", "SlowQuery")
Metric      = Model("query_analytics", "QueryMetric")
Reco        = Model("query_analytics", "IndexRecommendation")
Alert       = Model("query_analytics", "PerformanceAlert")
Sug         = Model("query_analytics", "QueryOptimizationSuggestion")
Plan        = Model("query_analytics", "QueryExecutionPlan")


class Command(BaseCommand):
    help = "Run the query-analytics pipelines manually (slow queries, alerts, recommendations, optimizations)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            default="all",
            choices=["slow", "opt", "alerts", "recs", "all"],
            help="Which pipeline to run.",
        )
        parser.add_argument("--user", type=str, default=None, help="UUID of the user to target.")
        parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default 7).")
        parser.add_argument("--limit", type=int, default=50, help="Max metrics to process per pipeline.")

    def handle(self, *args, **options):
        ptype       = options["type"]
        user_id     = options["user"]
        days        = options["days"]
        limit       = options["limit"]
        import datetime as dt
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)

        from apps.query_analytics.engines.index_engine        import generate_recommendations
        from apps.query_analytics.engines.optimization_engine import generate_suggestions

        self.stdout.write(self.style.SUCCESS(f"=== Run analytics [type={ptype}, since={days}d] ==="))

        targets = []
        if user_id:
            targets = [user_id]
        else:
            from django.contrib.auth import get_user_model
            targets = list(get_user_model().objects.values_list("id", flat=True)[:100])

        for uid in targets:
            if ptype in ("slow", "all"):
                self._run_slow(uid)
            if ptype in ("recs", "all"):
                created = generate_recommendations(str(uid))
                self._count("IndexRecommendation", created)
            if ptype in ("opt", "all"):
                created = generate_suggestions(str(uid))
                self._count("OptimizationSuggestion", created)

    def _run_slow(self, uid):
        from apps.query_analytics.engines.slow_query_engine import check_threshold
        qs = Metric.objects.filter(user_id=uid).order_by("-executed_at")[:500]
        seen = 0
        for m in qs:
            try:
                check_threshold(m)
                seen += 1
            except Exception:
                pass
        self.stdout.write(f"  Slow-query check: {seen} metrics processed for user {uid}")

    def _count(self, name: str, items):
        self.stdout.write(self.style.SUCCESS(
            f"  {name}: {len(items)} new items created."
        ))
