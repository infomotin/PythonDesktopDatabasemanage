from django.contrib import admin
from .models import DatabaseConnection, DatabaseServer


@admin.register(DatabaseConnection)
class DatabaseConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "engine", "host", "port", "dbname",
                    "connection_status", "last_connected", "created_at")
    list_filter = ("engine", "connection_status", "is_active", "created_at")
    search_fields = ("name", "dbname", "host", "user__email")
    readonly_fields = ("created_at", "updated_at", "last_connected", "connection_status")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("engine",)
        return self.readonly_fields


@admin.register(DatabaseServer)
class DatabaseServerAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "engine", "host", "port", "is_active", "created_at")
    list_filter = ("engine", "is_active")
    search_fields = ("name", "host")
