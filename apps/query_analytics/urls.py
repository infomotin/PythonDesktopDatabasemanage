from django.urls import path
from apps.query_analytics import views

app_name = "query_analytics"

urlpatterns = [
    path("", views.AnalyticsDashboard.as_view(), name="dashboard"),
    path("metrics/", views.MetricsLiveView.as_view(), name="metrics"),
    path("recommendations/", views.RecommendationsView.as_view(), name="recommendations"),
    path("execution-plans/", views.ExecutionPlansView.as_view(), name="execution_plans"),
    path("comparison/", views.PerformanceComparisonView.as_view(), name="comparison"),
    path("slow-queries/", views.SlowQueriesView.as_view(), name="slow_queries"),
    path("replay/<str:metric_id>/", views.QueryReplayView.as_view(), name="replay"),
    path("api/metrics/", views.MetricsAPI.as_view(), name="api_metrics"),
    path("api/recommendations/", views.RecommendationsAPI.as_view(), name="api_recommendations"),
    path("api/analyze/", views.AnalyzeQueryAPI.as_view(), name="api_analyze"),
    path("api/compare/", views.PerformanceComparisonAPI.as_view(), name="api_compare"),
    path("api/replay/", views.ReplayQueryAPI.as_view(), name="api_replay"),
    path("api/slow-queries/", views.SlowQueriesAPI.as_view(), name="api_slow_queries"),
    path("api/resource-snapshot/", views.ResourceSnapshotAPI.as_view(), name="api_resource_snapshot"),
    path("api/plan/", views.QueryPlanAPI.as_view(), name="api_plan"),
]
