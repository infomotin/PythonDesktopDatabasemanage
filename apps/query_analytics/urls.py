from django.urls import path
from . import views

app_name = "query_analytics"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    # Metrics
    path("metrics/",              views.MetricListView.as_view(),              name="metrics"),
    path("metrics/stream/",       views.MetricsStreamView.as_view(),           name="metrics_stream"),
    # Query history
    path("history/",              views.QueryHistoryView.as_view(),            name="history"),
    path("history/<uuid:pk>/",    views.QueryHistoryDetailView.as_view(),      name="history_detail"),
    path("history/<uuid:pk>/replay/", views.QueryReplayView.as_view(),      name="history_replay"),
    # Slow queries
    path("slow-queries/",         views.SlowQueryListView.as_view(),           name="slow_queries"),
    path("slow-queries/<uuid:pk>/", views.SlowQueryDetailView.as_view(),     name="slow_query_detail"),
    # Index recommendations
    path("recommendations/",      views.RecommendationListView.as_view(),      name="recommendations"),
    path("recommendations/<uuid:pk>/",        views.RecommendationDetailView.as_view(), name="recommendation_detail"),
    path("recommendations/<uuid:pk>/dismiss/", views.RecommendationDismissView.as_view(), name="recommendation_dismiss"),
    path("recommendations/<uuid:pk>/apply/",   views.RecommendationApplyView.as_view(),  name="recommendation_apply"),
    # Optimization suggestions
    path("optimizations/",        views.OptimizationSuggestionListView.as_view(), name="optimizations"),
    # Query comparison
    path("compare/",              views.QueryCompareView.as_view(),            name="compare"),
    path("compare/<uuid:pk>/",    views.QueryCompareDetailView.as_view(),      name="compare_detail"),
    # Resource monitor
    path("resources/",            views.ResourceMonitorView.as_view(),         name="resources"),
    # Performance alerts
    path("alerts/",               views.PerformanceAlertListView.as_view(),    name="alerts"),
    path("alerts/<uuid:pk>/ack/", views.AlertAcknowledgeView.as_view(),        name="alert_ack"),
    # Reports
    path("reports/",              views.ReportView.as_view(),                  name="reports"),
    path("reports/export/",       views.ReportExportView.as_view(),            name="reports_export"),
    # REST API
    path("api/analyze/",          views.AnalyzeQueryAPIView.as_view(),         name="analyze"),
    path("api/metrics/live/",     views.LiveMetricsAPIView.as_view(),          name="api_live_metrics"),
    path("api/metrics/summary/",  views.MetricsSummaryAPIView.as_view(),       name="api_metrics_summary"),
    path("api/recommendations/",  views.RecommendationsAPIView.as_view(),      name="api_recommendations"),
    path("api/alerts/",           views.AlertAPIView.as_view(),                name="api_alerts"),
    path("api/plans/<uuid:pk>/",  views.ExecutionPlanAPIView.as_view(),        name="api_plans"),
]
