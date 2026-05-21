from django.apps import AppConfig


class QueryAnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.query_analytics"
    verbose_name = "Query Analytics & Performance Monitoring"

    def ready(self):
        import apps.query_analytics.signals  # noqa: F401
