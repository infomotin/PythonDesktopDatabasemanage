import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class SavedQuery(models.Model):
    VISIBILITY_CHOICES = [("private", "Private"), ("team", "Team"), ("organization", "Organization"), ("public", "Public")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="saved_queries")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    raw_sql = models.TextField(blank=True, null=True)
    tag = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="private")
    category = models.CharField(max_length=50, blank=True)
    relation_ids = models.CharField(max_length=255, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=50, default="monthly")
    viewed_by = models.CharField(max_length=50, default="private")
    viewer_ids = models.CharField(max_length=255, blank=True)
    authentication_type = models.CharField(max_length=50, default="user")
    authentication_token = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


@admin.register(SavedQuery)
class QueryModelAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "visibility", "authentication_type", "created_at")
    list_filter = ("visibility", "authentication_type", "created_at")
    search_fields = ("name", "description", "raw_sql")
