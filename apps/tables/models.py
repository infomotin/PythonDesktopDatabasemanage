import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class VirtualDatabase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="managed_databases")
    name = models.CharField(max_length=255)
    engine = models.CharField(max_length=50, default="mysql")
    description = models.TextField(blank=True)
    row_count = models.BigIntegerField(default=0)
    total_size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.engine})"

    @property
    def tables_count(self):
        return self.tables.count()

    @property
    def total_size_mb(self):
        return round(self.total_size / (1024 * 1024), 2)

    @property
    def total_size_gb(self):
        return round(self.total_size / (1024 ** 3), 2)


class VirtualTable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    database = models.ForeignKey(VirtualDatabase, on_delete=models.CASCADE, related_name="tables")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    row_count = models.BigIntegerField(default=0)
    total_size = models.BigIntegerField(default=0)
    columns = models.JSONField(default=list, blank=True)
    indexes = models.JSONField(default=list, blank=True)
    primary_key = models.CharField(max_length=255, blank=True, null=True)
    is_synced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.database.name}.{self.name}"

    @property
    def total_size_mb(self):
        return round(self.total_size / (1024 * 1024), 2)


class TableRelationship(models.Model):
    TYPE_CHOICES = [("one_to_one", "One-to-One"), ("one_to_many", "One-to-Many"), ("many_to_many", "Many-to-Many")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_table = models.ForeignKey(VirtualTable, on_delete=models.CASCADE, related_name="source_relations")
    source_column = models.CharField(max_length=255)
    target_table = models.ForeignKey(VirtualTable, on_delete=models.CASCADE, related_name="target_relations")
    target_column = models.CharField(max_length=255)
    relation_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="one_to_many")
    on_delete = models.CharField(max_length=20, default="CASCADE")
    on_update = models.CharField(max_length=20, default="CASCADE")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("source_table", "source_column", "target_table", "target_column")]

    def __str__(self):
        return f"{self.source_table.name}.{self.source_column} → {self.target_table.name}.{self.target_column}"


@admin.register(VirtualDatabase)
class VirtualDatabaseAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "engine", "tables_count", "total_size_mb", "created_at")
    list_filter = ("engine", "created_at")
    search_fields = ("name", "user__email")


@admin.register(VirtualTable)
class VirtualTableAdmin(admin.ModelAdmin):
    list_display = ("name", "database", "row_count", "total_size_mb", "is_synced")
    list_filter = ("database__engine", "is_synced")
    search_fields = ("name", "database__name")



