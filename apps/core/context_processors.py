"""Caches the data."""


def dbms_settings(request):
    return {
        "DBMS_NAME": "DBMS Pro", "DBMS_VERSION": "1.0.0",
        "DBMS_DESCRIPTION": "Professional Database Management",
    }


def user_connections(request):
    from apps.connections.models import DatabaseConnection
    if request.user.is_authenticated:
        return {"user_connections": DatabaseConnection.objects.filter(user=request.user, is_active=True)}
    return {"user_connections": []}
