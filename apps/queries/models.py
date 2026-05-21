import uuid

from django.apps import AppConfig


class NotificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"


class WorkSpaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workspaces"


# ── extra models for queries / saved-queries ────────────────────────────────────

from django.db import models


class Queries(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="queries")
    query = models.TextField()
    query_type = models.CharField(max_length=55, default="SELECT")
    params = models.TextField(default="{}")
    success = models.BooleanField(default=True)
    execution_time = models.FloatField(default=0)
    affected_rows = models.BigIntegerField(default=0)
    result_columns = models.TextField(default="")
    result_preview = models.TextField(default="")
    error_message = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_duration = models.FloatField(default=0)
    auto_discovered_schema = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]
    def __str__(self):
        return f"{self.user.username} – {self.query_type} – {self.created_at:%Y-%m-%d %H:%M}"


# ── saved query ─────────────────────────────────────────────────────────────────

class SavedQueryModel(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="saved_query_models")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    raw_sql = models.TextField(blank=True, default="")
    slug = models.SlugField(max_length=255, blank=True)
    is_public = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    execution_count = models.IntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    execution_time_ms = models.FloatField(default=0)
    result_columns = models.TextField(default="")
    result_rows = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("user", "name")]

    def __str__(self):
        return f"{self.user.username} – {self.name}"


# ── query template ──────────────────────────────────────────────────────────────

class QueryTemplateModel(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_templates")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=50, blank=True)
    sql_content = models.TextField(blank=True, default="")
    engine_config = models.TextField(default="{}")
    metadata = models.TextField(default="{}")
    input_fields = models.TextField(default="[]")
    variables = models.TextField(default="[]")
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    is_public = models.BooleanField(default=False)
    execution_count = models.IntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ── otp ─────────────────────────────────────────────────────────────────────────

class OTPToken(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="otp_tokens")
    otp = models.CharField(max_length=10)
    purpose = models.CharField(max_length=30, default="login")
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} – {self.purpose}"

