from django.urls import path
from apps.subscription import views

app_name = "subscription"
urlpatterns = [
    path("", views.SubscriptionDashboard.as_view(), name="dashboard"),
    path("pricing/", views.PricingPage.as_view(), name="pricing"),
    path("billing/", views.BillingHistory.as_view(), name="billing"),
    path("upgrade/<str:tier>/", views.UpgradeSubscription.as_view(), name="upgrade"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("success/", views.PaymentSuccess.as_view(), name="success"),
    path("cancel/", views.PaymentCancel.as_view(), name="cancel"),
    path("webhook/", views.StripeWebhook.as_view(), name="webhook"),
    path("api/plans/", views.PlanListAPI.as_view(), name="api_plans"),
    path("api/upgrade/", views.UpgradeAPI.as_view(), name="api_upgrade"),
]
