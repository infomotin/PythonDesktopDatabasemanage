import uuid

from django.apps import AppConfig


class DbQueryHistoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.db_query_history"

