from django.core.cache import cache
from apps.connections.models import DatabaseConnection


def user_connections(request):
    if request.user.is_authenticated:
        conns = DatabaseConnection.objects.filter(user=request.user, is_active=True)
    else:
        conns = DatabaseConnection.objects.none()
    return {"user_connections": conns}
