

def user_subscription(request):
    from apps.subscription.models import Subscription
    if request.user.is_authenticated:
        try:
            sub = request.user.subscription_ref
        except Subscription.DoesNotExist:
            sub = None
    else:
        sub = None
    return {"user_subscription": sub}
