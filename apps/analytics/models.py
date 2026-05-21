import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalyticsEvent(models.Model):
    EVENT_TYPES = [
        ("query", _("Query")), ("import", _("Import")),
        ("export", _("Export")), ("seed", _("Seed")),
        ("login", _("Login")), ("alert", _("Alert")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="analytics_events", null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Analytics Event")
        verbose_name_plural = _("Analytics Events")

    def __str__(self):
        return f"{self.event_type} - {self.created_at:%Y-%m-%d %H:%M}"


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("description", "user__email")
