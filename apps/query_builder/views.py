import json, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView, View
from apps.query_builder.models import SavedQuery


class QueryBuilderView(LoginRequiredMixin, TemplateView):
    template_name = "query_builder/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = []
        return ctx


class CreateQueryView(LoginRequiredMixin, TemplateView):
    template_name = "query_builder/create.html"


class QueryHistoryView(LoginRequiredMixin, ListView):
    template_name = "query_builder/history.html"
    context_object_name = "history"
    paginate_by = 20

    def get_queryset(self):
        try:
            from apps.db_query_history.models import QueryHistory
            return QueryHistory.objects.filter(user=self.request.user)
        except Exception:
            return models.QuerySet.none()


class SavedQueriesView(LoginRequiredMixin, ListView):
    template_name = "query_builder/saved.html"
    context_object_name = "saved"
    paginate_by = 20

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class ExecuteQueryView(LoginRequiredMixin, TemplateView):
    template_name = "query_builder/execute.html"

    def post(self, request, *args, **kwargs):
        sql = request.POST.get("sql", "").strip()
        return self.get(request, sql=sql)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["result_columns"] = []
        ctx["result_rows"] = []
        ctx["row_count"] = 0
        return ctx


class QueryDetailView(LoginRequiredMixin, DetailView):
    template_name = "query_builder/detail.html"
    context_object_name = "query"

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class EditQueryView(LoginRequiredMixin, UpdateView):
    template_name = "query_builder/edit.html"
    model = SavedQuery
    fields = ["name", "description", "raw_sql", "tag", "visibility"]
    success_url = reverse_lazy("query_builder:saved")


class DeleteQueryView(LoginRequiredMixin, DeleteView):
    model = SavedQuery
    template_name = "query_builder/confirm_delete.html"
    success_url = reverse_lazy("query_builder:saved")

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class SchemaAPI(LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"schemata": []})


class ExecuteQueryAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        return JsonResponse({"columns": [], "rows": [], "row_count": 0, "execution_time": 0})


class ColumnNamesAPI(LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"columns": []})
