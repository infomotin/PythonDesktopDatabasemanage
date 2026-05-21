import uuid

from django.contrib import admin
from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone

from .models import (
    ConnectionSnapshot,
    MetricAggregate,
    PerformanceAlert,
    QueryComparison,
    QueryExecutionPlan,
    QueryLabel,
    QueryMetric,
    QueryOptimizationSuggestion,
    SlowQuery,
    IndexRecommendation,
)


# ---------------------------------------------------------------------------
# Helper mixin
# ---------------------------------------------------------------------------
class ReadOnlyMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QueryExecutionPlan)
class QueryExecutionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "engine", "total_cost", "execution_time_ms",
        "rows_examined", "rows_returned", "created_at",
    )
    list_filter = ("engine", "created_at")
    search_fields = ("plan_text", "engine")
    readonly_fields = ("created_at",)
    ordering = ["-created_at"]


@admin.register(QueryMetric)
class QueryMetricAdmin(admin.ModelAdmin):
    list_display = (
        "engine", "duration_ms", "rows_affected",
        "memory_consumed_mb", "cpu_percent",
        "status", "is_slow", "executed_at",
    )
    list_filter = ("engine", "status", "is_slow", "executed_at")
    search_fields = ("query_text", "error_message", "query_label")
    readonly_fields = ("created_at", "executed_at", "normalized_hash")
    ordering = ["-executed_at"]
    raw_id_fields = ("connection", "query_history", "execution_plan")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("connection", "query_history")


@admin.register(MetricAggregate)
class MetricAggregateAdmin(admin.ModelAdmin):
    list_display = (
        "user", "engine", "granularity",
        "bucket_start", "query_count", "avg_duration_ms",
    )
    list_filter = ("granularity", "engine", "bucket_start")
    search_fields = ("user__email",)
    ordering = ["-bucket_start"]


@admin.register(ConnectionSnapshot)
class ConnectionSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "connection", "timestamp", "state",
        "active_connections", "idle_connections",
        "total_connections", "usage_pct",
    )
    list_filter = ("state", "timestamp")
    search_fields = ("connection__name",)
    ordering = ["-timestamp"]

    @display(description=_("Usage %"))
    def usage_pct(self, obj):
        return f"{obj.usage_pct()}%"


@admin.register(SlowQuery)
class SlowQueryAdmin(admin.ModelAdmin):
    list_display = (
        "engine", "avg_duration_ms", "occurrence_count",
        "status", "last_seen", "first_seen",
    )
    list_filter = ("engine", "status", "last_seen")
    search_fields = ("query_text", "engine")
    ordering = ["-last_seen"]
    raw_id_fields = ("connection",)


@admin.register(IndexRecommendation)
class IndexRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "engine", "table_name", "column_names",
        "index_type", "score", "status",
        "estimated_improvement_pct", "created_at",
    )
    list_filter = ("engine", "index_type", "status", "created_at")
    search_fields = ("table_name", "create_statement", "rationale")
    ordering = ["-score", "-created_at"]
    raw_id_fields = ("connection",)
    filter_horizontal = ("slow_queries",)

    @display(description=_("Columns"))
    def column_names(self, obj):
        return ", ".join(obj.column_names)


@admin.register(QueryOptimizationSuggestion)
class QueryOptimizationSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "engine", "title", "suggestion_type",
        "estimated_improvement_pct", "confidence", "applied", "created_at",
    )
    list_filter = ("engine", "suggestion_type", "confidence", "applied", "created_at")
    search_fields = ("title", "description", "rationale")
    ordering = ["-estimated_improvement_pct", "-created_at"]
    raw_id_fields = ("query_metric", "slow_query", "execution_plan")


@admin.register(QueryComparison)
class QueryComparisonAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "winner_engine",
        "fastest_duration_ms", "avg_duration_ms", "created_at",
    )
    list_filter = ("created_at", "winner_engine")
    search_fields = ("name", "description")
    ordering = ["-created_at"]


@admin.register(PerformanceAlert)
class PerformanceAlertAdmin(admin.ModelAdmin):
    list_display = (
        "priority", "alert_type", "title",
        "connection", "acknowledged", "resolved", "created_at",
    )
    list_filter = ("priority", "alert_type", "acknowledged", "resolved", "created_at")
    search_fields = ("title", "message")
    ordering = ["-created_at"]
    list_editable = ("acknowledged", "resolved")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("connection", "user")


@admin.register(QueryLabel)
class QueryLabelAdmin(admin.ModelAdmin):
    list_display = (
        "label", "engine", "is_favorite",
        "connection", "user", "updated_at",
    )
    list_filter = ("engine", "is_favorite", "updated_at")
    search_fields = ("label", "description")
    ordering = ["-is_favorite", "-updated_at"]
    raw_id_fields = ("connection",)
