import json, uuid, csv, io
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.db import models
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, DetailView, FormView, View
from django.utils import timezone
from apps.uploads.services import (
    read_excel_to_dataframe, validate_excel_import, generate_excel,
    generate_csv, generate_excel_multisheet, coerce_types, clean_column_names,
    df_to_insert_sql, DataImportExportError,
)
from apps.connections.models import DatabaseConnection


class ImportExportDashboard(LoginRequiredMixin, TemplateView):
    template_name = "import_export/dashboard.html"


class ImportExcelView(LoginRequiredMixin, TemplateView):
    template_name = "import_export/import_excel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(user=self.request.user, is_active=True)
        return ctx

    def post(self, request):
        file_obj = request.FILES.get("excel_file")
        if not file_obj:
            messages.error(request, "Excel file is required.")
            return redirect("import_export:import_excel")
        try:
            tmp = settings.TEMP_DIR / f"{uuid.uuid4()}_{file_obj.name}"
            with open(tmp, "wb+") as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
            df = read_excel_to_dataframe(tmp)
            df = clean_column_names(df)
            preview = df.head(50).to_dict("records")
            columns = list(df.columns)
            job_id = str(uuid.uuid4())
            request.session["import_job"] = {"columns": columns, "file": str(tmp), "job_id": job_id}
            return render(request, "import_export/import_preview.html", {
                "columns": columns, "preview": preview, "job_id": job_id,
            })
        except Exception as exc:
            messages.error(request, f"Import failed: {exc}")
            return redirect("import_export:import_excel")


class ExportExcelView(LoginRequiredMixin, TemplateView):
    template_name = "import_export/export_excel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(user=self.request.user, is_active=True)
        return ctx

    def post(self, request):
        sql = request.POST.get("sql", "").strip()
        if not sql:
            messages.error(request, "SQL query is required for export.")
            return redirect("import_export:export_excel")
        try:
            import pandas as pd
            from io import StringIO
            df = pd.DataFrame([{"query": sql, "note": "Simulated export result"}])
        except Exception as exc:
            return HttpResponseBadRequest(f"Export failed: {exc}")
        wb = generate_excel(df, sheet_name="Export")
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="export.xlsx"'
        wb.save(response)
        return response


class ExcelToSQLView(LoginRequiredMixin, TemplateView):
    template_name = "import_export/excel_to_sql.html"

    def post(self, request):
        file_obj = request.FILES.get("excel_file")
        table_name = request.POST.get("table_name", "my_table")
        if not file_obj:
            messages.error(request, "Excel file is required.")
            return redirect("import_export:excel_to_sql")
        try:
            tmp = settings.TEMP_DIR / f"{uuid.uuid4()}_{file_obj.name}"
            with open(tmp, "wb+") as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
            df = read_excel_to_dataframe(tmp)
            df = clean_column_names(df)
            sql = df_to_insert_sql(df, table_name)
            return HttpResponse(sql, content_type="text/plain")
        except Exception as exc:
            return HttpResponseBadRequest(f"SQL generation failed: {exc}")


class ImportPreviewView(LoginRequiredMixin, TemplateView):
    template_name = "import_export/import_preview.html"


class ImportExcelAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        return JsonResponse({"job_id": str(uuid.uuid4()), "status": "queued"})


class ExportExcelAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        return JsonResponse({"url": "/exports/export.xlsx"})


class ImportExportTaskListView(LoginRequiredMixin, ListView):
    template_name = "import_export/task_list.html"
    context_object_name = "tasks"


class ImportExportTaskDetail(LoginRequiredMixin, DetailView):
    template_name = "import_export/task_detail.html"
    context_object_name = "task"
