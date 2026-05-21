import uuid
from decimal import Decimal
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, F, Sum, Count
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.connections.models import DatabaseConnection
from apps.databases.models import VirtualDatabase


User = get_user_model()

class SubscriptionTier(models.Model):
    class TierNames(models.TextChoices):
        FREE = "free", _("Free")
        PRO = "pro", _("Pro")
        ENTERPRISE = "enterprise", _("Enterprise")

    name = models.CharField(max_length=30, choices=TierNames.choices, unique=True)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    max_databases = models.IntegerField(default=1)
    max_tables = models.IntegerField(default=5)
    max_storage_gb = models.IntegerField(default=1)
    max_query_rows = models.IntegerField(default=1000)
    max_query_size_kb = models.IntegerField(default=64)
    allow_export = models.BooleanField(default=True)
    allow_advanced_query = models.BooleanField(default=False)
    allow_query_history = models.BooleanField(default=False)
    allow_sql_history = models.BooleanField(default=False)
    allow_collaboration = models.BooleanField(default=False)
    allow_api_access = models.BooleanField(default=False)
    allow_custom_dashboards = models.BooleanField(default=False)
    allow_data_seeding = models.BooleanField(default=False)
    allow_import_export = models.BooleanField(default=False)
    row_limit_per_view = models.IntegerField(default=100)
    stripe_price_id = models.CharField(max_length=255, blank=True, null=True)
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name

    @classmethod
    def get_tier(cls, name: str):
        try:
            return cls.objects.get(name=name, is_active=True)
        except cls.DoesNotExist:
            return cls.objects.filter(is_active=True).first()

    @classmethod
    def free(cls):
        return cls.get_tier("free")

    @classmethod
    def pro(cls):
        return cls.get_tier("pro")

    @classmethod
    def enterprise(cls):
        return cls.get_tier("enterprise")

    @staticmethod
    def _lim(val):
        return 0 if val in (0, -1) else val

    def within_limit(self, used: int, attr: str) -> bool:
        limit = getattr(self, f"max_{attr}", None)
        if limit <= 0:
            return True
        return used < limit

    def remaining(self, used: int, attr: str) -> int:
        limit = getattr(self, f"max_{attr}", None)
        if limit <= 0:
            return -1
        return max(0, limit - used)


class Subscription(models.Model):
    class Statuses(models.TextChoices):
        ACTIVE = "active", _("Active")
        CANCELED = "canceled", _("Canceled")
        PAST_DUE = "past_due", _("Past Due")
        UNPAID = "unpaid", _("Unpaid")
        TRIALING = "trialing", _("Trialing")
        INCOMPLETE = "incomplete", _("Incomplete")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    tier = models.ForeignKey(SubscriptionTier, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=Statuses.choices, default=Statuses.ACTIVE)
    external_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    billing_cycle = models.CharField(
        max_length=10,
        choices=[("monthly", _("Monthly")), ("yearly", _("Yearly"))],
        default="monthly",
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    last_payment_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.tier.name if self.tier else 'Unknown'}"

    @property
    def tier_name(self) -> str:
        return self.tier.name if self.tier else "free"

    @property
    def max_databases(self) -> int:
        return self.tier.max_databases if self.tier else 1

    @property
    def max_tables(self) -> int:
        return self.tier.max_tables if self.tier else 5

    @property
    def max_storage_gb(self) -> int:
        return self.tier.max_storage_gb if self.tier else 1

    @property
    def is_active(self) -> bool:
        return self.status == self.Statuses.ACTIVE

    @property
    def is_trialing(self) -> bool:
        return self.status == self.Statuses.TRIALING

    @property
    def is_canceled(self) -> bool:
        return self.status in (self.Statuses.CANCELED, self.Statuses.UNPAID)

    @property
    def is_paid(self) -> bool:
        return self.status in (self.Statuses.ACTIVE, self.Statuses.TRIALING)

    def databases_used(self) -> int:
        return DatabaseConnection.objects.filter(user=self.user).count()

    def can_add_database(self) -> bool:
        if self.tier and self.tier.max_databases <= 0:
            return True
        return self.databases_used() < self.max_databases

    def tables_used(self) -> int:
        return VirtualDatabase.objects.filter(user=self.user).aggregate(
            total=Count("tables")
        )["total"] or 0

    def can_add_table(self) -> bool:
        if self.tier and self.tier.max_tables <= 0:
            return True
        return self.tables_used() < self.max_tables

    def has_feature(self, feature: str) -> bool:
        if self.tier is None:
            return False
        return bool(getattr(self.tier, f"allow_{feature}", False))

    def storage_used_gb(self) -> float:
        total = VirtualDatabase.objects.filter(user=self.user).aggregate(
            total=Sum("size_bytes")
        )["total"] or 0
        return round(total / (1024 ** 3), 3)

    def storage_usage_pct(self) -> float:
        return (self.storage_used_gb() / self.max_storage_gb * 100) if self.max_storage_gb > 0 else 0

    def days_left(self) -> int:
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)

    def activate(self):
        now = timezone.now()
        self.status = self.Statuses.ACTIVE
        self.current_period_start = now
        self.current_period_end = now + timezone.timedelta(days=30)
        self.save(update_fields=["status", "current_period_start", "current_period_end"])

    def cancel(self):
        now = timezone.now()
        self.cancel_at_period_end = True
        self.canceled_at = now
        self.save(update_fields=["cancel_at_period_end", "canceled_at"])


class BillingEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="billing_events")
    event_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="USD")
    provider = models.CharField(max_length=30, blank=True, null=True)
    provider_event_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending")
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} - {self.amount} {self.currency}"


class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    tier = models.ForeignKey(SubscriptionTier, on_delete=models.SET_NULL, null=True)
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    max_uses = models.IntegerField(default=0)
    used_count = models.IntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    @property
    def is_valid_discount(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_until and self.valid_until < now:
            return False
        if self.valid_from and self.valid_from > now:
            return False
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False
        return True

    def apply(self):
        self.used_count = F("used_count") + 1
        self.save(update_fields=["used_count"])
