from django.contrib import admin
from .models import DatabaseConnection, DatabaseServer


@admin.register(DatabaseConnection)
class DatabaseConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "engine", "host", "port", "dbname", "is_active", "last_connected", "created_at")
    list_filter = ("engine", "is_active", "created_at")
    search_fields = ("name", "dbname", "host", "user__email")
    readonly_fields = ("created_at", "updated_at", "last_connected")


@admin.register(DatabaseServer)
class DatabaseServerAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "engine", "host", "port", "is_active")
    list_filter = ("engine", "is_active")
    search_fields = ("name", "host")
