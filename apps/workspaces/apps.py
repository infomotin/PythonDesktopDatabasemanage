import uuid

from django.apps import AppConfig


class QueriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.queries"


class QueriesManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.queries_manager"


class SeedsManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.seeds_manager"


class CoreEnforcerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core_enforcer"


class JointConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.joint"
