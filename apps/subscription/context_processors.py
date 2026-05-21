def user_subscription(request):
    if not request.user.is_authenticated:
        return {"subscription": None, "tier_limits": {}}
    sub = getattr(request.user, "subscription", None)
    return {"subscription": sub, "tier_limits": getattr(sub, "tier", None) and {}}

