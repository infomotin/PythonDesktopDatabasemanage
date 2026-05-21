import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    USER_ROLE_CHOICES = [
        ("superuser", _("Super User")),
        ("admin", _("Admin")),
        ("developer", _("Developer")),
        ("analyst", _("Analyst")),
        ("readonly", _("Read Only")),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default="developer")
    phone = models.CharField(max_length=20, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
    login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def is_administrator(self):
        return self.role in ("superuser", "admin")

    @property
    def subscription(self):
        from apps.subscription.models import Subscription
        try:
            return self.subscription_ref
        except Subscription.DoesNotExist:
            return None

    def can_access_database(self, database) -> bool:
        from apps.connections.models import DatabaseConnection
        if self.is_administrator:
            return True
        if not hasattr(self, "subscription_ref"):
            return False
        sub = getattr(self, "subscription_ref", None)
        if not sub:
            return False
        return (
            getattr(sub.tier, "name", "") == "enterprise"
            or getattr(database, "user_id", None) == self.id
        )

    def get_max_databases(self) -> int:
        if self.is_administrator:
            return -1
        try:
            sub = self.subscription_ref
        except Exception:
            return 1
        if not sub or not sub.tier:
            return 1
        return sub.tier.max_databases

    def can_access_feature(self, feature: str) -> bool:
        try:
            sub = self.subscription_ref
        except Exception:
            return feature in ("query_builder", "analytics")
        if not sub or not sub.tier:
            return feature in ("query_builder", "analytics")
        return bool(getattr(sub.tier, f"allow_{feature}", False))
