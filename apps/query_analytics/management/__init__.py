"""Management command: cleanup_old_metrics

Usage:
    python manage.py cleanup_old_metrics [--days N] [--dry-run]

Purges old QueryExecutionMetric, QueryHistoryEntry, ResourceSnapshot, and
QueryPlanCache rows beyond the retention window.
"""

import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from apps.query_analytics.models import (
    QueryExecutionMetric,
    QueryHistoryEntry,
    ResourceSnapshot,
    QueryPlanCache,
    SlowQueryAlert,
)


_RETENTION_DAYS: int = int(getattr(settings, "QA_METRIC_RETENTION_DAYS", 365))
_BATCH: int = 5000


class Command(BaseCommand):
    help = "Purge expired query analytics metrics per retention policy."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=_RETENTION_DAYS,
                            help=f"Retention period in days (default {_RETENTION_DAYS})")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be deleted without deleting anything.")

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - datetime.timedelta(days=days)
        tag = "[DRY RUN] " if dry_run else ""
        verbosity = options["verbosity"]

        models_to_purge = [
            ("QueryExecutionMetric", QueryExecutionMetric),
            ("QueryHistoryEntry", QueryHistoryEntry),
            ("ResourceSnapshot", ResourceSnapshot),
            ("QueryPlanCache", QueryPlanCache),
            ("SlowQueryAlert", SlowQueryAlert),
        ]

        total_deleted = 0
        for label, model_cls in models_to_purge:
            qs = model_cls.objects.filter(created_at__lt=cutoff)
            count = qs.count()
            if verbosity >= 1:
                self.stdout.write(f"{tag}{label} rows older than {days} days: {count}")
            if not dry_run and count:
                deleted = 0
                while True:
                    ids = list(qs.values_list("id", flat=True)[:_BATCH])
                    if not ids:
                        break
                    r, _ = model_cls.objects.filter(id__in=ids).delete()
                    deleted += r.get(f"query_analytics.{label}", 0)
                self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} {label} rows."))
                total_deleted += deleted

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(f"Total deleted: {total_deleted} rows."))
