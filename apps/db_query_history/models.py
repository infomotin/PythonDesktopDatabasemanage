import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class QueryHistory(models.Model):
    QueryTYPE = [ ("select", "SELECT"), ("insert", "INSERT"), ("update", "UPDATE"),
                  ("delete", "DELETE"), ("create", "CREATE"), ("drop", "DROP"),
                  ("alter", "ALTER"), ("other", "OTHER") ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_history")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True)
    database = models.ForeignKey("databases.ManagedDatabase", on_delete=models.SET_NULL, null=True, blank=True)
    query = models.TextField()
    query_type = models.CharField(max_length=20, choices=QueryTYPE, default="other")
    params = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    execution_time = models.FloatField(default=0)
    affected_rows = models.BigIntegerField(default=0)
    result_columns = models.JSONField(default=list, blank=True)
    result_preview = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True, null=True)
    has_data = models.BooleanField(default=False)
    row_count = models.BigIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_duration = models.FloatField(default=0)
    auto_discovered_schema = models.BooleanField(default=False)
    is_saved = models.BooleanField(default=False)
    has_error = models.BooleanField(default=False)
    is_error = models.BooleanField(default=False)
    column_names = models.JSONField(default=list, blank=True)
    human_readable_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Query History")
        verbose_name_plural = _("Query History")
        ordering = ["-completed_at"]

    def __str__(self):
        ts = str(self.completed_at) if self.completed_at else self.query_type
        return f"{self.user.email} - {ts}"

    @property
    def is_error(self):
        return not self.success and self.error_message


@admin.register(QueryHistory)
class QueryAdmin(admin.ModelAdmin):
    list_display = ("user", "connection", "query_type", "success", "execution_time", "row_count", "completed_at")
    list_filter = ("success", "query_type", "connection", "completed_at")
    search_fields = ("query", "error_message", "user__email")
    readonly_fields = ("completed_at", "completed_duration")
    ordering = ["-completed_at"]

