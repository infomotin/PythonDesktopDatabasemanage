import uuid

from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


# --- Accounts & Auth ---

class UserActivationToken(models.Model):
    user = models.OneToOneField("users.User", on_delete=models.CASCADE, related_name="activation_token")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Activation for {self.user.email}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Password reset for {self.user.user.username}"


# --- Invites ---

class Invite(models.Model):
    STATUS_CHOICES = [("pending", _("Pending")), ("accepted", _("Accepted")), ("expired", _("Expired")), ("revoked", _("Revoked"))]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inviter = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="invites_sent")
    email = models.EmailField()
    role = models.CharField(max_length=20, default="developer")
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey("workspaces.Organization", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    invitee = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="invites_received")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    message = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite '{self.email}' from {self.inviter.user.username}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("email", "inviter", "role", "status", "workspace", "expires_at", "created_at")
    list_filter = ("status", "role", "created_at")
    search_fields = ("email", "inviter__email")
