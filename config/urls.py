from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

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
    path("api/", include("apps.core.api_urls")),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="users/password_reset.html"
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="users/password_reset_done.html"
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="users/password_reset_confirm.html"
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="users/password_reset_complete.html"
    ), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

try:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
except ImportError:
    pass
