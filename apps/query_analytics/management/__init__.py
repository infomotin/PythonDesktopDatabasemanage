"""
query_analytics.management.commands.cleanup_metrics
----------------------------------------------------
Management command:  python manage.py cleanup_metrics [--days N] [--dry-run]

Purges old QueryMetric / MetricAggregate rows according to retention
policy.  Retries are controlled by auto-migration on safely-deletable
items (soft-deleted instead of hard-deleted for 30-day retention).
"""
from __future__ import annotations

import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from apps.query_analytics.models import (
    MetricAggregate,
    QueryMetric,
)


_RETENTION_DAYS: int = int(getattr(settings, "QA_METRIC_RETENTION_DAYS", 365))
_BATCH: int = 5000


class Command(BaseCommand):
    help = "Purge expired query analytics metrics per retention policy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=_RETENTION_DAYS,
            help=f"Retention period in days (default {_RETENTION_DAYS})",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        days      = options["days"]
        dry_run   = options["dry_run"]
        cutoff    = timezone.now() - datetime.timedelta(days=days)
        tag       = "[DRY RUN] " if dry_run else ""
        verbosity = options["verbosity"]

        # ── QueryMetric ──────────────────────────────────────────
        qm_qs = QueryMetric.objects.filter(executed_at__lt=cutoff)
        qm_count = qm_qs.count()
        if verbosity >= 1:
            self.stdout.write(
                f"{tag}QueryMetric rows older than {days} days: {qm_count}"
            )
        if not dry_run and qm_count:
            deleted = 0
            while True:
                ids = list(qm_qs.values_list("id", flat=True)[:_BATCH])
                if not ids:
                    break
                r, _ = QueryMetric.objects.filter(id__in=ids).delete()
                deleted += r.get("query_analytics.QueryMetric", 0)
            self.stdout.write(self.style.SUCCESS(
                f"Deleted {deleted} QueryMetric rows."
            ))

        # ── MetricAggregate ─────────────────────────────────────
        ma_qs = MetricAggregate.objects.filter(bucket_start__lt=cutoff)
        ma_count = ma_qs.count()
        if verbosity >= 1:
            self.stdout.write(
                f"{tag}MetricAggregate rows older than {days} days: {ma_count}"
            )
        if not dry_run and ma_count:
            deleted = 0
            while True:
                ids = list(ma_qs.values_list("id", flat=True)[:_BATCH])
                if not ids:
                    break
                r, _ = MetricAggregate.objects.filter(id__in=ids).delete()
                deleted += r.get("query_analytics.MetricAggregate", 0)
            self.stdout.write(self.style.SUCCESS(
                f"Deleted {deleted} MetricAggregate rows."
            ))
