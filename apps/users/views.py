import json, os
import logging
from pathlib import Path
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as login_user, logout as logout_user, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseNotFound
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.core.paginator import Paginator, EmptyPage
from django.utils.text import slugify
from django.db.models import Count, Q, Sum
from django.core.mail import send_mail

from apps.users.forms import UserRegistrationForm, UserProfileForm, ChangePasswordForm
logger = logging.getLogger(__name__)
User = get_user_model()


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login_user(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.POST.get("next", "")
            return redirect(next_url or "dashboard:index")
        messages.error(request, "Invalid email or password.")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", {"form": form, "page_title": "Sign In"})

@login_required
def logout_view(request):
    logout_user(request)
    messages.info(request, "You have been logged out.")
    return redirect("users:login")

@require_http_methods(["GET", "POST"])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email_verified = True
            user.save()
            login_user(request, user)
            msg = f"Welcome, {user.get_full_name() or user.username}!"
            messages.success(request, msg + " Your account has been created.")
            try:
                send_mail(
                    "Welcome to DBMS Pro!", msg,
                    settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True,
                )
            except Exception:
                pass
            return redirect("dashboard:index")
        messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegistrationForm()
    return render(request, "users/signup.html", {"form": form, "page_title": "Create Account"})

@login_required
def profile(request):
    return render(request, "users/profile.html", {
        "page_title": "Profile",
        "user": request.user,
    })

@login_required
@require_POST
def edit_profile(request):
    form = UserProfileForm(request.POST, request.FILES, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
    else:
        messages.error(request, "Please correct the errors.")
    return redirect("users:profile")

@login_required
@require_POST
def change_password(request):
    form = ChangePasswordForm(request.user, request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Password changed successfully.")
    else:
        messages.error(request, "Please correct the errors.")
    return redirect("users:profile")
