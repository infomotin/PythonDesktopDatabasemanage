import json, time, uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, View
from django.utils import timezone
from apps.seeding.models import SeedJob
from apps.connections.models import DatabaseConnection
from apps.tables.models import VirtualDatabase, VirtualTable


class SeedingDashboard(LoginRequiredMixin, TemplateView):
    template_name = "seeding/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["jobs"] = SeedJob.objects.filter(user=self.request.user).order_by("-created_at")[:20]
        return ctx


class SchemaSelectorView(LoginRequiredMixin, TemplateView):
    template_name = "seeding/schema_selector.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(
            user=self.request.user, is_active=True
        )
        ctx["databases"] = VirtualDatabase.objects.filter(user=self.request.user)
        return ctx


class SeedPreviewView(LoginRequiredMixin, TemplateView):
    template_name = "seeding/preview.html"

    def post(self, request):
        return self.get(request)


class RunSeedView(LoginRequiredMixin, TemplateView):
    template_name = "seeding/run.html"

    def post(self, request, *args, **kwargs):
        try:
            schema = json.loads(request.POST.get("schema", "{}"))
            config = json.loads(request.POST.get("config", "{}"))
        except Exception:
            schema = {}
            config = {}
        job = SeedJob.objects.create(
            user=request.user,
            status="pending",
            schema=schema,
            config=config,
            connection=DatabaseConnection.objects.filter(
                user=request.user, pk=request.POST.get("connection_id")
            ).first(),
        )
        messages.success(request, f"Seed job {job.id} queued.")
        return redirect("seeding:dashboard")


class SeedHistoryView(LoginRequiredMixin, ListView):
    template_name = "seeding/history.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return SeedJob.objects.filter(user=self.request.user).order_by("-created_at")


class GetSchemaAPI(LoginRequiredMixin, View):
    def get(self, request):
        conn_id = request.GET.get("connection_id")
        db_id = request.GET.get("database_id")
        return JsonResponse({"tables": [], "columns": {}, "relationships": []})


class RunSeedAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        job = SeedJob.objects.create(
            user=request.user,
            status="running",
            schema=data.get("schema", {}),
            config=data.get("config", {}),
        )
        return JsonResponse({"job_id": str(job.id), "status": "running"})
