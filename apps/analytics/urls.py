from django.urls import path
from apps.analytics import views

app_name = "analytics"
urlpatterns = [
    path("", views.AnalyticsDashboard.as_view(), name="dashboard"),
    path("table/<uuid:table_id>/", views.TableAnalyticsView.as_view(), name="table"),
    path("table/<uuid:table_id>/stats/", views.TableStatsAPI.as_view(), name="table_stats"),
    path("edge/<uuid:run_id>/", views.EdgeNodeStatsView.as_view(), name="edge_stats"),
    path("api/kpis/", views.KPIStatsAPI.as_view(), name="kpis_api"),
    path("api/query/<uuid:run_id>/", views.QueryStatsAPI.as_view(), name="query_stats"),
]
