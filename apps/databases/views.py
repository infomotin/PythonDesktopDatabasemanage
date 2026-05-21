import uuid, json, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from apps.connections.models import DatabaseConnection
from apps.databases.models import ManagedDatabase, DataStoragePointModel
from apps.core.crypto import decrypt_credential
from apps.connections.utils import ConnectionPool


User = None


class DatabaseListView(LoginRequiredMixin, ListView):
    template_name = "databases/database_list.html"
    context_object_name = "databases"
    paginate_by = 20

    def get_queryset(self):
        return ManagedDatabase.objects.filter(owner=self.request.user)


class DatabaseCreateView(LoginRequiredMixin, CreateView):
    model = ManagedDatabase
    fields = ["name", "engine", "type", "description", "is_visible"]
    template_name = "databases/database_form.html"
    success_url = reverse_lazy("databases:list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class DatabaseDetailView(LoginRequiredMixin, DetailView):
    model = ManagedDatabase
    template_name = "databases/database_detail.html"
    context_object_name = "database"

    def get_queryset(self):
        return ManagedDatabase.objects.filter(owner=self.request.user)


class DatabaseUpdateView(LoginRequiredMixin, UpdateView):
    model = ManagedDatabase
    fields = ["name", "engine", "type", "description", "is_visible"]
    template_name = "databases/database_form.html"
    success_url = reverse_lazy("databases:list")

    def get_queryset(self):
        return ManagedDatabase.objects.filter(owner=self.request.user)


class DatabaseDeleteView(LoginRequiredMixin, DeleteView):
    model = ManagedDatabase
    template_name = "databases/database_confirm_delete.html"
    context_object_name = "database"
    success_url = reverse_lazy("databases:list")

    def get_queryset(self):
        return ManagedDatabase.objects.filter(owner=self.request.user)


class DatabaseTablesView(LoginRequiredMixin, DetailView):
    model = ManagedDatabase
    template_name = "databases/database_tables.html"
    context_object_name = "database"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tables"] = self.object.tables.filter(is_deleted=False)
        return ctx


class StoragePointView(LoginRequiredMixin, DetailView):
    model = ManagedDatabase
    template_name = "databases/storage_points.html"
    context_object_name = "database"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["storage_points"] = self.object.tables.filter(is_deleted=False)
        return ctx


class DatabaseActionCommitView(LoginRequiredMixin, TemplateView):
    template_name = "databases/database_action.html"

    def post(self, request, pk):
        db = get_object_or_404(ManagedDatabase, pk=pk, owner=request.user)
        action = request.POST.get("action")
        messages.info(request, f"Action '{action}' queued for {db.name}.")
        return redirect("databases:detail", pk=db.pk)


class DatabaseListAPI(LoginRequiredMixin, TemplateView):
    def get(self, request):
        dbs = ManagedDatabase.objects.filter(owner=request.user).values(
            "id", "name", "engine", "type", "row_count", "is_visible", "created_at"
        )
        return JsonResponse({"databases": list(dbs)})
