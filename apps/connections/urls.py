from django.urls import path
from . import views

app_name = "connections"
urlpatterns = [
    path("", views.ConnectionListView.as_view(), name="list"),
    path("create/", views.ConnectionCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.ConnectionDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", views.ConnectionUpdateView.as_view(), name="update"),
    path("<uuid:pk>/delete/", views.ConnectionDeleteView.as_view(), name="delete"),
    path("<uuid:pk>/execute/", views.ExecuteQueryView.as_view(), name="execute"),
    path("<uuid:pk>/clone/", views.CloneConnectionView.as_view(), name="clone"),
    path("test-raw/", views.TestConnectionRawView.as_view(), name="test_raw"),
]
