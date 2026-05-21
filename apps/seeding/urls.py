from django.urls import path
from apps.seeding import views

app_name = "seeding"
urlpatterns = [
    path("", views.SeedingDashboard.as_view(), name="dashboard"),
    path("schemas/", views.SchemaSelectorView.as_view(), name="schema_selector"),
    path("preview/", views.SeedPreviewView.as_view(), name="preview"),
    path("run/", views.RunSeedView.as_view(), name="run"),
    path("history/", views.SeedHistoryView.as_view(), name="history"),
    path("api/schema/", views.GetSchemaAPI.as_view(), name="api_schema"),
    path("api/run/", views.RunSeedAPI.as_view(), name="api_run"),
]
