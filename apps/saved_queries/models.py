import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class SavedQuery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="saved_queries")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    raw_sql = models.TextField(blank=True, default="")
    tag = models.CharField(max_length=255, blank=True)
    visibility = models.CharField(max_length=20, default="private",
        choices=[("private", "Private"), ("team", "Team"), ("organization", "Organization"), ("public", "Public")])
    category = models.CharField(max_length=50, blank=True)
    relation_ids = models.CharField(max_length=255, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=50, default="monthly")
    viewed_by = models.CharField(max_length=50, blank=True)
    viewer_ids = models.CharField(max_length=255, blank=True)
    authentication_type = models.CharField(max_length=50, default="user")
    authentication_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "name")]
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class QueryModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sql_content = models.TextField(blank=True)
    schema_content = models.JSONField(default=dict, blank=True)
    purpose = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True


class QueryExecution(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField(null=True, blank=True)
    query_id = models.BigIntegerField(null=True, blank=True)
    query_text = models.TextField()
    execution_time_ms = models.FloatField(null=True, blank=True)
    affected_rows = models.BigIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    result_data = models.JSONField(null=True, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Query Execution")
        ordering = ["-executed_at"]

    def __str__(self):
        return f"Query {self.id} @ {self.executed_at.strftime('%Y-%m-%d %H:%M')} (user {self.user_id})"


class QueryTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_templates")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, blank=True)
    sql_content = models.TextField()
    engine_config = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    input_fields = models.JSONField(default=list, blank=True)
    variables = models.JSONField(default=list, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    is_public = models.BooleanField(default=False)
    execution_count = models.IntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        order_with_respect_to = "name"

    def __str__(self):
        return self.name


@admin.register(QueryTemplate)
class QueryTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category", "is_public", "execution_count", "created_at")
    list_filter = ("category", "is_public", "created_at")
    search_fields = ("name", "description", "category", "sql_content")
    ordering = ["-created_at"]
