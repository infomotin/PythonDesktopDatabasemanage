import uuid

from django.utils.translation import gettext_lazy as _
from .models import Notification


def create_notification(user, type_: str, title: str, message: str, action_url: str = None, action_label: str = None):
    return Notification.objects.create(
        user=user,
        type=type_,
        title=title,
        message=message,
        action_url=action_url,
        action_label=action_label,
    )
