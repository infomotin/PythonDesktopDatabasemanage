import json, time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, TemplateView
from apps.connections.utils import ConnectionPool


class QueryListView(LoginRequiredMixin, ListView):
    template_name = "queries/query_list.html"
    context_object_name = "history"
    paginate_by = 20

    def get_queryset(self):
        try:
            from apps.db_query_history.models import QueryHistory
            return QueryHistory.objects.filter(user=self.request.user)
        except Exception:
            return models.QuerySet.none()


class QueryDetailView(LoginRequiredMixin, DetailView):
    template_name = "queries/query_detail.html"
    context_object_name = "query"

    def get_queryset(self):
        try:
            from apps.db_query_history.models import QueryHistory
            return QueryHistory.objects.filter(user=self.request.user)
        except Exception:
            return models.QuerySet.none()


class QueryResultsView(LoginRequiredMixin, DetailView):
    template_name = "queries/query_results.html"
    context_object_name = "query"

    def get_queryset(self):
        try:
            from apps.db_query_history.models import QueryHistory
            return QueryHistory.objects.filter(user=self.request.user)
        except Exception:
            return models.QuerySet.none()


class ImportSQLFromExcelView(LoginRequiredMixin, TemplateView):
    template_name = "queries/import_sql.html"


class QueryModelView(LoginRequiredMixin, ListView):
    template_name = "queries/query_model_list.html"
    context_object_name = "models"

    def get_queryset(self):
        return []


class QueryTemplateView(LoginRequiredMixin, ListView):
    template_name = "queries/query_template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        return []
