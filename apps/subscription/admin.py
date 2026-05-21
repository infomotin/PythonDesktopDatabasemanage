import uuid

from django.contrib import admin
from django.db import models
from .models import SubscriptionTier, Subscription, BillingEvent, DiscountCode


@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    list_display = ("name", "price_monthly", "max_databases", "max_tables", "max_storage_gb", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "tier", "status", "current_period_end", "cancel_at_period_end", "created_at")
    list_filter = ("status", "tier", "created_at")
    search_fields = ("user__email", "external_id")
    readonly_fields = ("created_at", "updated_at", "external_id")


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ("subscription", "event_type", "amount", "currency", "status", "provider", "created_at")
    list_filter = ("event_type", "status", "provider")
    search_fields = ("subscription__user__email", "provider_event_id")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "tier", "discount_pct", "used_count", "max_uses", "is_active", "valid_until")
    list_filter = ("is_active", "tier")
    search_fields = ("code",)
