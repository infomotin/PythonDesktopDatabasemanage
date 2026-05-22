import json, time

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView, View

from apps.connections.models import DatabaseConnection
from apps.core.adapters.factory import EngineFactory
from apps.core.crypto import decrypt_credential
from apps.db_query_history.models import QueryHistory
from apps.query_builder.forms import SavedQueryForm
from apps.query_builder.models import SavedQuery


class QueryBuilderView(LoginRequiredMixin, TemplateView):
    template_name = "query_builder/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(user=self.request.user, is_active=True)
        ctx["saved_queries"] = SavedQuery.objects.filter(user=self.request.user).order_by("-updated_at")[:10]
        return ctx


class CreateQueryView(LoginRequiredMixin, CreateView):
    template_name = "query_builder/create.html"
    model = SavedQuery
    form_class = SavedQueryForm
    success_url = reverse_lazy("query_builder:saved")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class QueryHistoryView(LoginRequiredMixin, ListView):
    template_name = "query_builder/history.html"
    context_object_name = "history"
    paginate_by = 20

    def get_queryset(self):
        try:
            return QueryHistory.objects.filter(user=self.request.user).order_by("-created_at")
        except Exception:
            return models.QuerySet.none()


class SavedQueriesView(LoginRequiredMixin, ListView):
    template_name = "query_builder/saved.html"
    context_object_name = "saved"
    paginate_by = 20

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user).order_by("-updated_at")


class ExecuteQueryView(LoginRequiredMixin, TemplateView):
    template_name = "query_builder/execute.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(user=self.request.user, is_active=True)
        ctx["sql"] = kwargs.get("sql", "")
        ctx["result_columns"] = kwargs.get("result_columns", [])
        ctx["result_rows"] = kwargs.get("result_rows", [])
        ctx["row_count"] = kwargs.get("row_count", 0)
        ctx["execution_time"] = kwargs.get("execution_time", 0)
        ctx["error"] = kwargs.get("error")
        ctx["selected_connection"] = kwargs.get("selected_connection")
        return ctx

    def post(self, request, *args, **kwargs):
        connection_id = request.POST.get("connection_id")
        sql = request.POST.get("sql", "").strip()
        if not sql:
            messages.error(request, "SQL query is required.")
            return redirect("query_builder:execute")

        connection = get_object_or_404(DatabaseConnection, pk=connection_id, user=request.user)
        password = decrypt_credential(connection.password)
        adapter = EngineFactory.create(connection.engine, connection.host, connection.port, connection.dbname, connection.username, password)
        if adapter is None:
            messages.error(request, f"Unsupported engine: {connection.engine}")
            return redirect("query_builder:execute")

        start = time.time()
        try:
            columns, rows = adapter.execute(sql)
            execution_time = round(time.time() - start, 3)
            QueryHistory.objects.create(
                user=request.user,
                connection=connection,
                query=sql,
                query_type=sql.split()[0].upper() if sql.split() else "OTHER",
                success=True,
                execution_time=execution_time,
                affected_rows=len(rows),
                result_columns=columns,
                result_preview=rows[:100],
                error_message="",
                has_data=len(rows) > 0,
                row_count=len(rows),
                completed_at=timezone.now(),
                completed_duration=execution_time,
            )
            return self.render_to_response({
                "sql": sql,
                "connections": DatabaseConnection.objects.filter(user=request.user, is_active=True),
                "result_columns": columns,
                "result_rows": rows,
                "row_count": len(rows),
                "execution_time": execution_time,
                "error": None,
                "selected_connection": connection,
            })
        except Exception as exc:
            messages.error(request, f"Query execution failed: {exc}")
            return redirect("query_builder:execute")


class QueryDetailView(LoginRequiredMixin, DetailView):
    template_name = "query_builder/detail.html"
    context_object_name = "query"
    pk_url_kwarg = "query_id"

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class EditQueryView(LoginRequiredMixin, UpdateView):
    template_name = "query_builder/edit.html"
    model = SavedQuery
    form_class = SavedQueryForm
    success_url = reverse_lazy("query_builder:saved")
    pk_url_kwarg = "query_id"

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class DeleteQueryView(LoginRequiredMixin, DeleteView):
    model = SavedQuery
    template_name = "query_builder/confirm_delete.html"
    success_url = reverse_lazy("query_builder:saved")
    pk_url_kwarg = "query_id"

    def get_queryset(self):
        return SavedQuery.objects.filter(user=self.request.user)


class SchemaAPI(LoginRequiredMixin, View):
    def get(self, request):
        connection_id = request.GET.get("connection_id")
        if not connection_id:
            return JsonResponse({"error": "connection_id required"}, status=400)
        connection = get_object_or_404(DatabaseConnection, pk=connection_id, user=request.user)
        password = decrypt_credential(connection.password)
        adapter = EngineFactory.create(connection.engine, connection.host, connection.port, connection.dbname, connection.username, password)
        if adapter is None:
            return JsonResponse({"error": f"Unsupported engine: {connection.engine}"}, status=400)
        return JsonResponse(adapter.get_schema())


class ExecuteQueryAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        sql = body.get("sql", "").strip()
        connection_id = body.get("connection_id")
        if not sql or not connection_id:
            return JsonResponse({"error": "connection_id and sql are required"}, status=400)

        connection = get_object_or_404(DatabaseConnection, pk=connection_id, user=request.user)
        password = decrypt_credential(connection.password)
        adapter = EngineFactory.create(connection.engine, connection.host, connection.port, connection.dbname, connection.username, password)
        if adapter is None:
            return JsonResponse({"error": f"Unsupported engine: {connection.engine}"}, status=400)

        start = time.time()
        try:
            columns, rows = adapter.execute(sql)
            execution_time = round(time.time() - start, 3)
            QueryHistory.objects.create(
                user=request.user,
                connection=connection,
                query=sql,
                query_type=sql.split()[0].upper() if sql.split() else "OTHER",
                success=True,
                execution_time=execution_time,
                affected_rows=len(rows),
                result_columns=columns,
                result_preview=rows[:100],
                error_message="",
                has_data=len(rows) > 0,
                row_count=len(rows),
                completed_at=timezone.now(),
                completed_duration=execution_time,
            )
            return JsonResponse({
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time": execution_time,
            })
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


class ColumnNamesAPI(LoginRequiredMixin, View):
    def get(self, request):
        connection_id = request.GET.get("connection_id")
        table = request.GET.get("table")
        if not connection_id:
            return JsonResponse({"error": "connection_id required"}, status=400)
        connection = get_object_or_404(DatabaseConnection, pk=connection_id, user=request.user)
        password = decrypt_credential(connection.password)
        adapter = EngineFactory.create(connection.engine, connection.host, connection.port, connection.dbname, connection.username, password)
        if adapter is None:
            return JsonResponse({"error": f"Unsupported engine: {connection.engine}"}, status=400)
        schema = adapter.get_schema()
        columns = []
        if table:
            for item in schema.get("tables", []):
                if item.get("name") == table:
                    columns = item.get("columns", [])
                    break
        return JsonResponse({"columns": columns})
