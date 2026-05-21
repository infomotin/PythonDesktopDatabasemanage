from django.urls import path
from . import views

app_name = "connections"
urlpatterns = [
    path("", views.ConnectionListView.as_view(), name="list"),
    path("create/", views.ConnectionCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.ConnectionDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", views.ConnectionUpdateView.as_view(), name="update"),
    path("<uuid:pk>/delete/", views.ConnectionDeleteView.as_view(), name="delete"),
    path("<uuid:pk>/test/", views.TestConnectionView.as_view(), name="test"),
    path("<uuid:pk>/execute/", views.ExecuteQueryView.as_view(), name="execute"),
    path("execute/", views.ExecuteQueryView.as_view(), name="execute_ajax"),
    path("test/", views.TestConnectionRawView.as_view(), name="test_raw"),
    path("clone/<uuid:pk>/", views.CloneConnectionView.as_view(), name="clone"),
]
