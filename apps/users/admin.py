from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ("email", "username", "first_name", "last_name", "role", "email_verified", "is_active", "created_at")
    list_filter = ("role", "email_verified", "is_active", "is_staff", "created_at")
    search_fields = ("email", "username", "first_name", "last_name", "company")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (_("Personal Info"), {"fields": ("first_name", "last_name", "role", "phone", "company", "avatar")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Security"), {"fields": ("two_factor_enabled", "email_verified", "login_attempts", "locked_until", "last_login_ip")}),
        (_("Preferences"), {"fields": ("preferences",)}),
        (_("Important Dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "role"),
        }),
    )
