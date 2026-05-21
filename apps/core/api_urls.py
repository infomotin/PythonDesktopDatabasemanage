from django.urls import path
from apps.core.api import views as api_views

app_name = "api"
urlpatterns = [
    path("connections/test/", api_views.TestConnectionAPI.as_view(), name="api_connection_test"),
    path("connections/schema/", api_views.GetSchemaAPI.as_view(), name="api_schema"),
    path("notifications/unread/", api_views.NotificationUnreadAPI.as_view(), name="api_notifications_unread"),
]
