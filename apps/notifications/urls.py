from django.urls import path
from apps.notifications import views

app_name = "notifications"
urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("mark-read/<uuid:pk>/", views.MarkReadView.as_view(), name="mark_read"),
    path("mark-all-read/", views.MarkAllReadView.as_view(), name="mark_all_read"),
    path("unread-count/", views.UnreadCountView.as_view(), name="unread_count"),
    path("api/unread/", views.UnreadCountAPI.as_view(), name="api_unread"),
]
