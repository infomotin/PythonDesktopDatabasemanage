import uuid

from django.apps import AppConfig


class VirtualDatabasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.virtual_databases"

