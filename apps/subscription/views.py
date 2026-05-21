import json, time
import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    TemplateView, ListView, DetailView, FormView, View,
)
from apps.subscription.models import SubscriptionTier, Subscription, BillingEvent, DiscountCode
from apps.users.models import User


stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionDashboard(LoginRequiredMixin, TemplateView):
    template_name = "subscription/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            sub = self.request.user.subscription_ref
        except Exception:
            sub = None
        ctx["subscription"] = sub
        ctx["tiers"] = SubscriptionTier.objects.filter(is_active=True)
        return ctx


class PricingPage(TemplateView):
    template_name = "subscription/pricing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tiers"] = SubscriptionTier.objects.filter(is_active=True)
        try:
            ctx["current_tier"] = self.request.user.subscription_ref.tier
        except Exception:
            ctx["current_tier"] = None
        return ctx


class BillingHistory(LoginRequiredMixin, ListView):
    template_name = "subscription/billing_history.html"
    context_object_name = "events"
    paginate_by = 20

    def get_queryset(self):
        try:
            sub = self.request.user.subscription_ref
            return BillingEvent.objects.filter(subscription=sub).order_by("-created_at")
        except Exception:
            return BillingEvent.objects.none()


class UpgradeSubscription(LoginRequiredMixin, View):
    def post(self, request, tier):
        try:
            sub = request.user.subscription_ref
        except Exception:
            sub = None
        if sub:
            sub.tier = SubscriptionTier.objects.filter(name=tier, is_active=True).first()
            sub.save()
        messages.success(request, f"Subscription tier updated to {tier}.")
        return redirect("subscription:dashboard")


class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = "subscription/checkout.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tier_id = self.request.GET.get("tier") or kwargs.get("tier")
        if tier_id:
            ctx["tier"] = get_object_or_404(SubscriptionTier, pk=tier_id, is_active=True)
        else:
            ctx["tier"] = None
        return ctx

    def post(self, request):
        return redirect("subscription:success")


class PaymentSuccess(LoginRequiredMixin, TemplateView):
    template_name = "subscription/success.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["subscription"] = getattr(request.user, "subscription_ref", None)
        return ctx


class PaymentCancel(LoginRequiredMixin, TemplateView):
    template_name = "subscription/cancel.html"


class StripeWebhook(View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode())
            event = stripe.Event.construct_from(body, stripe.api_key)
        except Exception:
            return JsonResponse({"received": True})
        return JsonResponse({"received": True})


class PlanListAPI(LoginRequiredMixin, View):
    def get(self, request):
        tiers = SubscriptionTier.objects.filter(is_active=True)
        data = [{"name": t.name, "price": str(t.price_monthly),
                 "databases": t.max_databases, "tables": t.max_tables} for t in tiers]
        return JsonResponse({"plans": data})


class UpgradeAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body)
            tier_id = body.get("tier_id")
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        try:
            sub = request.user.subscription_ref
        except Exception:
            sub = None
        if not sub:
            msg = "No active subscription."
            return JsonResponse({"error": msg}, status=400)
        tier = SubscriptionTier.objects.filter(pk=tier_id, is_active=True).first()
        if not tier:
            return JsonResponse({"error": "Tier not found."}, status=404)
        sub.tier = tier
        sub.status = Subscription.Statuses.ACTIVE
        sub.save()
        return JsonResponse({"subscription_id": str(sub.id), "tier": tier.name, "status": "ok"})
