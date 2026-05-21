import json, time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models, connection as dj_conn
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, View
from apps.tables.models import VirtualDatabase, VirtualTable, TableRelationship
from apps.connections.models import DatabaseConnection


class TableView(LoginRequiredMixin, ListView):
    template_name = "tables/table_list.html"
    context_object_name = "tables"
    paginate_by = 30

    def get_queryset(self):
        db_id = self.request.GET.get("database")
        qs = VirtualTable.objects.filter(database__user=self.request.user)
        if db_id:
            qs = qs.filter(database_id=db_id)
        return qs.select_related("database")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["databases"] = VirtualDatabase.objects.filter(user=self.request.user)
        return ctx


class TableDetailView(LoginRequiredMixin, DetailView):
    model = VirtualTable
    template_name = "tables/table_detail.html"
    context_object_name = "table"

    def get_queryset(self):
        return VirtualTable.objects.filter(database__user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["columns"] = self.object.columns or []
        ctx["indexes"] = self.object.indexes or []
        ctx["relationships"] = self.object.source_relations.all() | self.object.target_relations.all()
        return ctx


class TableRowEditView(LoginRequiredMixin, View):
    def post(self, request, table_id):
        table = get_object_or_404(VirtualTable, pk=table_id, database__user=request.user)
        row_id = request.POST.get("row_id")
        messages.info(request, f"Edit row {row_id} on {table.name}.")
        return redirect("tables:detail", table_id=table.pk)


class TableRowDeleteView(LoginRequiredMixin, View):
    def post(self, request, table_id):
        table = get_object_or_404(VirtualTable, pk=table_id, database__user=request.user)
        row_id = request.POST.get("row_id")
        messages.info(request, f"Delete row {row_id} from {table.name}.")
        return redirect("tables:detail", table_id=table.pk)


class DownloadTableView(LoginRequiredMixin, DetailView):
    model = VirtualTable
    template_name = "tables/table_download.html"
    context_object_name = "table"

    def get_queryset(self):
        return VirtualTable.objects.filter(database__user=self.request.user)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        import csv
        from io import StringIO
        cols = self.object.columns or []
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        rows = [{"col": r} for r in range(10)]
        for row in rows:
            writer.writerow([row.get("col", "") for _ in cols])
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.object.name}.csv"'
        return response


class TableSchemaAPI(LoginRequiredMixin, View):
    def get(self, request):
        table_id = request.GET.get("table_id")
        table = get_object_or_404(VirtualTable, pk=table_id, database__user=request.user)
        return JsonResponse({"columns": table.columns, "indexes": table.indexes,
                             "primary_key": table.primary_key})


class IndexSuggestionAPI(LoginRequiredMixin, View):
    def get(self, request):
        table_id = request.GET.get("table_id")
        table = get_object_or_404(VirtualTable, pk=table_id, database__user=request.user)
        return JsonResponse({"suggestions": ["Consider indexing 'id'", "Consider indexing 'created_at'"]})
