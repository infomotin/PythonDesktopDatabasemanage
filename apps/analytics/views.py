import json, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, View
from django.core.paginator import Paginator


class AnalyticsDashboard(LoginRequiredMixin, TemplateView):
    template_name = "analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stats"] = {
            "total_databases": 0,
            "total_queries": 0,
            "avg_query_time": 0,
            "total_rows": 0,
        }
        return ctx


class TableAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/table_analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        table_id = kwargs.get("table_id")
        ctx["table_id"] = table_id
        ctx["stats"] = {}
        return ctx


class TableStatsAPI(LoginRequiredMixin, View):
    def get(self, request, table_id):
        return JsonResponse({"table_id": str(table_id), "row_count": 0, "column_count": 0})


class EdgeNodeStatsView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/edge_stats.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        run_id = kwargs.get("run_id")
        ctx["run_id"] = run_id
        ctx["stats"] = {}
        return ctx


class KPIStatsAPI(LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"databases": 0, "queries": 0, "rows": 0, "storage_mb": 0})


class QueryStatsAPI(LoginRequiredMixin, View):
    def get(self, request, run_id):
        return JsonResponse({"run_id": str(run_id), "status": "unknown"})
