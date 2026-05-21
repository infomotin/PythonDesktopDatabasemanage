from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from apps.query_analytics.models import QueryExecutionMetric, QueryHistoryEntry
from apps.query_analytics.services.ai_optimizer import bulk_analyse
from apps.query_analytics.services.index_recommender import generate_recommendations
from apps.subscription.models import SubscriptionTier


class Command(BaseCommand):
    help = "Analyse slow queries and generate AI+index recommendations."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7,
                            help="Look back N days for slow queries")
        parser.add_argument("--threshold", type=float, default=500.0,
                            help="Duration threshold in ms for slow query detection")

    def handle(self, *args, **options):
        days = options["days"]
        threshold = options["threshold"]
        cutoff = timezone.now() - timezone.timedelta(days=days)

        self.stdout.write(f"Looking at queries from the last {days} days (threshold {threshold}ms)…")

        slow = list(QueryExecutionMetric.objects.filter(
            duration_ms__gte=threshold, created_at__gte=cutoff,
        ).select_related("user", "connection")[:500])

        if not slow:
            self.stdout.write(self.style.WARNING("No slow queries found."))
            return

        users_seen = set()
        ai_count = 0
        idx_count = 0

        for metric in slow:
            user = metric.user
            if user not in users_seen:
                tier_name = "free"
                try:
                    sub = user.subscription_ref
                    tier_name = getattr(sub.tier, "name", "free") if sub and sub.tier else "free"
                except Exception:
                    pass
                if tier_name in ("premium", "enterprise"):
                    suggestions = bulk_analyse(user, metric.database_engine, threshold_ms=threshold)
                    ai_count += len(suggestions)
                users_seen.add(user)

            if metric.connection:
                engine = metric.connection.engine
                db = metric.connection.dbname
                recs = generate_recommendations(user, engine, db, [metric])
                for rec in recs:
                    rec.save()
                    idx_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. AI suggestions: {ai_count}. Index recommendations saved: {idx_count}."
        ))
