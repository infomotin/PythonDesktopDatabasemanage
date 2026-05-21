from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.dashboard.urls")),
    path("users/", include("apps.users.urls")),
    path("connections/", include("apps.connections.urls")),
    path("databases/", include("apps.databases.urls")),
    path("tables/", include("apps.tables.urls")),
    path("query-builder/", include("apps.query_builder.urls")),
    path("import-export/", include("apps.import_export.urls")),
    path("seeding/", include("apps.seeding.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("subscription/", include("apps.subscription.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("queries/", include("apps.queries.urls")),
    path("api/", include("apps.core.api_urls")),
    path("api/", include("apps.connections.urls")),
    path("api/", include("apps.databases.urls")),
    path("password-reset/", include("django.contrib.auth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

try:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
except ImportError:
    pass
