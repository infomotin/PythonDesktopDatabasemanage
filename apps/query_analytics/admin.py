import uuid

from django.contrib import admin
from django.contrib.admin import display
from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    QueryExecutionMetric, QueryHistoryEntry, QueryReplayRecord,
    PerformanceComparison, IndexRecommendation, SlowQueryAlert,
    QueryPlanCache, ResourceSnapshot, QueryPattern,
    AIOptimizationSuggestion, TierFeatureUsage,
)


class ReadOnlyMetricsMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(QueryExecutionMetric)
class QueryExecutionMetricAdmin(admin.ModelAdmin):
    list_display = ("query_type", "database_engine", "duration_ms", "rows_returned",
                    "memory_mb", "cpu_ms", "status", "created_at")
    list_filter = ("query_type", "database_engine", "status", "created_at")
    search_fields = ("raw_sql", "error_message", "user__email", "query_fingerprint")
    readonly_fields = ("query_fingerprint", "duration_ms", "memory_mb", "cpu_ms",
                       "rows_affected", "rows_returned", "created_at")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    list_per_page = 50


@admin.register(QueryHistoryEntry)
class QueryHistoryEntryAdmin(admin.ModelAdmin):
    list_display = ("query_type", "user", "connection", "duration_ms",
                    "rows_affected", "success", "created_at")
    list_filter = ("query_type", "success", "created_at")
    search_fields = ("raw_sql", "error_message", "user__email")
    readonly_fields = ("query_fingerprint", "created_at")
    date_hierarchy = "created_at"
    ordering = ["-created_at"]


@admin.register(QueryReplayRecord)
class QueryReplayRecordAdmin(admin.ModelAdmin):
    list_display = ("original", "duration_ms", "rows_affected",
                    "rows_returned", "status", "replayed_at")
    list_filter = ("status", "replayed_at")
    search_fields = ("original__raw_sql", "error_message")
    ordering = ["-replayed_at"]
    raw_id_fields = ("original",)
    readonly_fields = ("replayed_at",)


@admin.register(PerformanceComparison)
class PerformanceComparisonAdmin(admin.ModelAdmin):
    list_display = ("name", "engine_a", "duration_a_ms", "engine_b",
                    "duration_b_ms", "winner", "delta_pct", "created_at")
    list_filter = ("engine_a", "engine_b", "created_at")
    search_fields = ("name", "logical_sql", "winner")
    ordering = ["-created_at"]


@admin.register(IndexRecommendation)
class IndexRecommendationAdmin(admin.ModelAdmin):
    list_display = ("table_name", "database_engine", "index_type",
                    "score", "estimated_improvement_pct", "priority", "status", "created_at")
    list_filter = ("priority", "status", "database_engine", "index_type")
    search_fields = ("table_name", "database_name", "rationale", "column_names")
    ordering = ["-score", "-created_at"]
    list_per_page = 50

    @display(description=_("Columns"))
    def col_names(self, obj):
        return ", ".join(obj.column_names)


@admin.register(SlowQueryAlert)
class SlowQueryAlertAdmin(admin.ModelAdmin):
    list_display = ("severity", "threshold_ms", "message", "is_read", "created_at")
    list_filter = ("severity", "is_read", "created_at")
    search_fields = ("message",)
    raw_id_fields = ("user", "metric")
    ordering = ["-created_at"]
    list_editable = ("is_read",)


@admin.register(QueryPlanCache)
class QueryPlanCacheAdmin(admin.ModelAdmin):
    list_display = ("query_fingerprint", "database_engine", "estimated_cost",
                    "estimated_rows", "actual_rows", "last_used_at")
    list_filter = ("database_engine", "plan_version")
    search_fields = ("query_fingerprint", "plan_summary")
    ordering = ["-last_used_at"]
    readonly_fields = ("query_fingerprint", "last_used_at")
    raw_id_fields = ("connection",)


@admin.register(ResourceSnapshot)
class ResourceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("connection", "pool_usage_pct", "cpu_usage_pct",
                    "memory_mb_used", "active_connections", "has_bottleneck", "created_at")
    list_filter = ("has_bottleneck", "created_at")
    search_fields = ("bottleneck_reason", "connection__name")
    raw_id_fields = ("user", "connection")
    ordering = ["-created_at"]

    @display(description=_("Pool %"))
    def pool_usage_pct(self, obj):
        return f"{obj.pool_usage_pct:.1f}%"

    @display(description=_("CPU %"))
    def cpu_usage_pct(self, obj):
        return f"{obj.cpu_usage_pct:.1f}%"

    @display(description=_("Memory MB"))
    def memory_mb_used(self, obj):
        return f"{obj.memory_mb_used:.1f} MB"


@admin.register(QueryPattern)
class QueryPatternAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "query_type", "total_executions",
                    "avg_duration_ms", "p95_duration_ms", "last_executed_at")
    list_filter = ("query_type", "engine")
    search_fields = ("fingerprint", "sample_sql")
    ordering = ["-p95_duration_ms"]
    readonly_fields = ("fingerprint", "total_executions", "avg_duration_ms")
    raw_id_fields = ("user", "connection")


@admin.register(AIOptimizationSuggestion)
class AIOptimizationSuggestionAdmin(admin.ModelAdmin):
    list_display = ("suggestion_type", "title", "confidence_score",
                    "estimated_improvement_pct", "status", "created_at")
    list_filter = ("suggestion_type", "status", "database_engine")
    search_fields = ("title", "rationale", "original_sql", "optimized_sql")
    ordering = ["-confidence_score", "-created_at"]
    list_editable = ("status",)
    raw_id_fields = ("user", "metric")


@admin.register(TierFeatureUsage)
class TierFeatureUsageAdmin(admin.ModelAdmin):
    list_display = ("user", "feature", "tier", "day", "count", "limit")
    list_filter = ("feature", "tier", "day")
    search_fields = ("user__email",)
    ordering = ["-day", "user"]
    raw_id_fields = ("user",)
