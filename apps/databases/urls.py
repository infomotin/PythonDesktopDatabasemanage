from django.urls import path
from apps.databases import views

app_name = "databases"
urlpatterns = [
    path("", views.DatabaseListView.as_view(), name="list"),
    path("create/", views.DatabaseCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.DatabaseDetailView.as_view(), name="detail"),
    path("<uuid:pk>/tables/", views.DatabaseTablesView.as_view(), name="tables"),
    path("<uuid:pk>/edit/", views.DatabaseUpdateView.as_view(), name="edit"),
    path("<uuid:pk>/delete/", views.DatabaseDeleteView.as_view(), name="delete"),
    path("<uuid:pk>/actions/", views.DatabaseActionCommitView.as_view(), name="action"),
    path("<uuid:pk>/storage-points/", views.StoragePointView.as_view(), name="storage_points"),
    path("api/list/", views.DatabaseListAPI.as_view(), name="api_list"),
]
