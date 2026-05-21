import os
from django.conf import settings
from django.core.cache import cache
from apps.connections.models import DatabaseConnection


def dbms_settings(request):
    return {
        "DBMS_NAME": getattr(settings, "DBMS_NAME", "DBMS Pro"),
        "DBMS_VERSION": getattr(settings, "DBMS_VERSION", "1.0.0"),
        "DBMS_DESCRIPTION": getattr(settings, "DBMS_DESCRIPTION", "Professional Database Management System"),
    }


def user_connections(request):
    if request.user.is_authenticated:
        conns = DatabaseConnection.objects.filter(user=request.user, is_active=True)
    else:
        conns = DatabaseConnection.objects.none()
    return {"user_connections": conns}
