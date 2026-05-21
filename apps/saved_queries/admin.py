from django.contrib import admin
from .models import QueryExecution, QueryTemplate, TriggerNode, UserTrigger, UserAction


@admin.register(QueryExecution)
class QueryExecutionAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "query_id", "executed_at", "execution_time_ms", "affected_rows")
    list_filter = ("success", "executed_at")
    search_fields = ("query_text", "error_message")
    ordering = ["-executed_at"]


@admin.register(QueryTemplate)
class QueryTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "category", "is_public", "execution_count", "created_at")
    list_filter = ("category", "is_public")
    search_fields = ("name", "description", "sql_content")


@admin.register(TriggerNode)
class TriggerNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "service_type", "is_active", "created_at")
    list_filter = ("service_type", "is_active")
    search_fields = ("name",)


@admin.register(UserTrigger)
class UserTriggerAdmin(admin.ModelAdmin):
    list_display = ("user", "trigger", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "trigger__name")


@admin.register(UserAction)
class UserActionAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "node_id", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "user__username")
