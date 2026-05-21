import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class ManagedDatabase(models.Model):
    DISPLAY_TYPES = [
        ("table", _("Table")),
        ("view", _("View")),
        ("materialized_view", _("Materialized View")),
        ("function", _("Function")),
        ("procedure", _("Procedure")),
        ("schema", _("Schema")),
        ("database", _("Database")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="databases")
    engine = models.CharField(max_length=50, default="postgresql")
    type = models.CharField(max_length=30, choices=DISPLAY_TYPES, default="table")
    table_schema = models.CharField(max_length=100, blank=True)
    created_by = models.CharField(max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    size = models.FloatField(default=0)
    total_size = models.FloatField(default=0)
    table_size = models.FloatField(default=0)
    index_size = models.FloatField(default=0)
    row_count = models.BigIntegerField(default=0)
    live_rows_estimate = models.FloatField(default=0)
    is_visible = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def human_size(self):
        if self.total_size <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(self.total_size) < 1024:
                return f"{self.total_size:.1f} {unit}"
            self.total_size /= 1024
        return f"{self.total_size:.1f} PB"


class DataStoragePointModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    database = models.ForeignKey(ManagedDatabase, on_delete=models.CASCADE, related_name="tables")  # Corrected
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255, blank=True)
    engine = models.CharField(max_length=50, blank=True)
    table_schema = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    size = models.FloatField(default=0)
    table_size = models.FloatField(default=0)
    total_size = models.FloatField(default=0)
    index_size = models.FloatField(default=0)
    row_count = models.BigIntegerField(default=0)
    live_rows_estimate = models.FloatField(default=0)
    is_visible = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def human_size(self):
        if self.total_size <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(self.total_size) < 1024:
                return f"{self.total_size:.1f} {unit}"
            self.total_size /= 1024
        return f"{self.total_size:.1f} PB"


@admin.register(ManagedDatabase)
class ManagedDatabaseAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "type", "engine", "row_count", "human_size", "created_at")
    list_filter = ("type", "engine", "is_visible", "created_at")
    search_fields = ("name", "owner__email", "table_schema", "external_id")
    ordering = ["name"]


@admin.register(DataStoragePointModel)
class DSPAdmin(admin.ModelAdmin):
    list_display = ("name", "database", "owner", "engine", "row_count", "total_size", "is_visible")
    list_filter = ("is_visible", "is_deleted", "created_at")
    search_fields = ("name", "owner", "engine")


