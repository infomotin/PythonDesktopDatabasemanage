import uuid, datetime
from django.urls import reverse
from django.utils import timezone

def send_verification_email(user, domain):
    from django.core.mail import send_mail
    from django.conf import settings
    uid = uuid.uuid4().hex
    link = f"https://{domain}{reverse('activate', args=[uid])}"
    subject = "Verify your account"
    body = f"Hi {user.first_name or user.username},\nPlease verify: {link}"
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return True


def send_welcome_email(user):
    from django.core.mail import send_mail
    from django.conf import settings
    send_mail("Welcome!", f"Welcome {user.first_name or ''}!", settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return True


def send_invite_email(invite, domain):
    from django.core.mail import send_mail
    from django.conf import settings
    link = f"https://{domain}{reverse('accept-invite', args=[str(invite.token)])}"
    send_mail("You're invited!", f"Accept: {link}", settings.DEFAULT_FROM_EMAIL, [invite.email], fail_silently=True)
    return True


def send_password_reset_email(user, domain, token):
    from django.core.mail import send_mail
    from django.conf import settings
    link = f"https://{domain}{reverse('password_reset_confirm', args=[token])}"
    send_mail("Reset your password", link, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return True


def send_login_detected_email(user, ip, ua):
    from django.core.mail import send_mail
    from django.conf import settings
    send_mail("New login", f"IP: {ip}\nUA: {ua}", settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    return True
