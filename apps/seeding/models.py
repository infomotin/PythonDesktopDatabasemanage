import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SeedJob(models.Model):
    STATUS_CHOICES = [
        ("pending", _("Pending")),
        ("running", _("Running")),
        ("completed", _("Completed")),
        ("failed", _("Failed")),
        ("canceled", _("Canceled")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="seed_jobs")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True)
    database = models.ForeignKey("databases.VirtualDatabase", on_delete=models.CASCADE, null=True, blank=True)
    schema = models.JSONField(default=dict, blank=True)
    config = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Seed {self.database} @ {self.created_at}"
