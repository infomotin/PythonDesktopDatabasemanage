from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse


class TestConnectionAPI(LoginRequiredMixin, APIView):
    def get(self, request):
        try:
            from apps.connections.utils import test_connection
            engine = request.GET.get("engine", "sqlite")
            ok, msg = test_connection(
                engine=engine, host=request.GET.get("host", "localhost"),
                port=int(request.GET.get("port", 3306)),
                dbname=request.GET.get("database", ""),
                username=request.GET.get("username", ""),
                password=request.GET.get("password", ""),
            )
            return Response({"success": ok, "message": msg}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class GetSchemaAPI(LoginRequiredMixin, APIView):
    def get(self, request):
        return Response({"tables": [], "columns": {}})


class NotificationUnreadAPI(LoginRequiredMixin, APIView):
    def get(self, request):
        from apps.notifications.models import Notification
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})
