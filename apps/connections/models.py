import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class DatabaseConnection(models.Model):
    ENGINE_CHOICES = [
        ("mysql", _("MySQL")), ("postgresql", _("PostgreSQL")),
        ("oracle", _("Oracle")), ("mongodb", _("MongoDB")),
        ("sqlite", _("SQLite")), ("sqlserver", _("SQL Server")),
        ("mariadb", _("MariaDB")), ("cockroachdb", _("CockroachDB")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="connections")
    name = models.CharField(max_length=255)
    engine = models.CharField(max_length=30, choices=ENGINE_CHOICES)
    host = models.CharField(max_length=255, default="localhost")
    port = models.IntegerField(default=3306)
    dbname = models.CharField(max_length=255)
    username = models.CharField(max_length=255, blank=True)
    password = models.TextField(blank=True, help_text=_("Encrypted database password"))
    options = models.JSONField(default=dict, blank=True)
    query_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_connected = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_engine_display()})"

    @admin.display(description=_("Password"))
    def masked_password(self):
        from apps.core.crypto import decrypt_credential
        try:
            val = decrypt_credential(self.password)
        except Exception:
            val = self.password
        return "••••••••" if val else "—"


class DatabaseServer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="db_servers")
    name = models.CharField(max_length=255)
    engine = models.CharField(max_length=30, choices=DatabaseConnection.ENGINE_CHOICES)
    host = models.CharField(max_length=255, default="localhost")
    port = models.IntegerField(default=3306)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "name")]
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
