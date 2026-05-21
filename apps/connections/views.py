import uuid, json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import (
    JsonResponse, HttpResponse, StreamingHttpResponse,
    HttpResponseForbidden, HttpResponseBadRequest,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView,
    TemplateView,
)
from apps.core.crypto import encrypt_credential, decrypt_credential
from apps.connections.utils import create_django_engine, ConnectionPool, test_connection
from apps.connections.models import DatabaseConnection, DatabaseServer


from django.contrib.auth import get_user_model
User = get_user_model()


class ConnectionListView(LoginRequiredMixin, ListView):
    model = DatabaseConnection
    template_name = "connections/connection_list.html"
    context_object_name = "connections"
    paginate_by = 20

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)


class ConnectionCreateView(LoginRequiredMixin, CreateView):
    model = DatabaseConnection
    fields = ["name", "engine", "host", "port", "dbname", "username", "password", "options"]
    template_name = "connections/connection_form.html"
    success_url = reverse_lazy("connections:list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        if form.cleaned_data.get("password"):
            form.instance.password = encrypt_credential(form.cleaned_data["password"])
        response = super().form_valid(form)
        messages.success(self.request, f"Connection '{self.object.name}' created.")
        return response


class ConnectionDetailView(LoginRequiredMixin, DetailView):
    model = DatabaseConnection
    template_name = "connections/connection_detail.html"
    context_object_name = "connection"

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)


class ConnectionUpdateView(LoginRequiredMixin, UpdateView):
    model = DatabaseConnection
    fields = ["name", "engine", "host", "port", "dbname", "username", "password", "options", "is_active"]
    template_name = "connections/connection_form.html"
    success_url = reverse_lazy("connections:list")

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)

    def form_valid(self, form):
        if form.cleaned_data.get("password"):
            form.instance.password = encrypt_credential(form.cleaned_data["password"])
        response = super().form_valid(form)
        messages.success(self.request, f"Connection '{self.object.name}' updated.")
        return response


class ConnectionDeleteView(LoginRequiredMixin, DeleteView):
    model = DatabaseConnection
    template_name = "connections/connection_confirm_delete.html"
    context_object_name = "connection"
    success_url = reverse_lazy("connections:list")

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        name = self.get_object().name
        response = super().delete(request, *args, **kwargs)
        messages.info(request, f"Connection '{name}' deleted.")
        return response


class TestConnectionView(LoginRequiredMixin, DetailView):
    model = DatabaseConnection
    template_name = "connections/connection_test.html"
    context_object_name = "connection"

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        pwd = decrypt_credential(self.object.password)
        ok, msg = test_connection(
            self.object.engine, self.object.host,
            self.object.port, self.object.dbname,
            self.object.username, pwd,
        )
        self.object.last_connected = timezone.now() if ok else None
        self.object.save(update_fields=["last_connected"])
        if ok:
            messages.success(request, f"Connected successfully: {msg}")
        else:
            messages.error(request, f"Connection failed: {msg}")
        return redirect("connections:detail", pk=self.object.pk)


class TestConnectionRawView(LoginRequiredMixin, TemplateView):
    template_name = "connections/connection_test.html"
    extra_context = {}

    def get(self, request, *args, **kwargs):
        return redirect("connections:create")


class ExecuteQueryView(LoginRequiredMixin, TemplateView):
    template_name = "connections/execute_query.html"

    def get_queryset(self):
        return DatabaseConnection.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        connection = None
        if pk:
            connection = get_object_or_404(DatabaseConnection, pk=pk, user=request.user)
        connections = DatabaseConnection.objects.filter(user=request.user, is_active=True)
        return self.render_to_response({
            "connection": connection,
            "connections": connections,
            "executed_at": None,
            "error": None,
            "result_columns": [],
            "result_rows": [],
            "row_count": 0,
            "execution_time": 0,
            "sql": "",
        })

    def post(self, request, pk=None):
        connection = None
        if pk:
            connection = get_object_or_404(DatabaseConnection, pk=pk, user=request.user)
        conn_id = request.POST.get("connection_id") or (str(connection.pk) if connection else "")
        sql = request.POST.get("sql", "").strip()
        if not sql:
            messages.error(request, "SQL query is required.")
            return redirect("connections:execute")

        conn_obj = get_object_or_404(DatabaseConnection, pk=conn_id, user=request.user)
        pwd = decrypt_credential(conn_obj.password)
        ok, msg = test_connection(
            conn_obj.engine, conn_obj.host,
            conn_obj.port, conn_obj.dbname,
            conn_obj.username, pwd,
        )
        if not ok:
            messages.error(request, f"Database not reachable: {msg}")
            return redirect("connections:execute")

        alias = ConnectionPool.get(conn_obj)
        try:
            start = timezone.now()
            with models.connections[alias].cursor() as cursor:
                cursor.execute(sql)
                cols = [c[0] for c in cursor.description] if cursor.description else []
                rows = [list(r) for r in cursor.fetchall()]
            elapsed = (timezone.now() - start).total_seconds()
            result_columns = cols
            result_rows = rows
            row_count = len(rows)
            error = None
            executed_at = timezone.now()
            conn_obj.query_count = models.F("query_count") + 1
            conn_obj.save(update_fields=["query_count"])
            messages.success(request, f"Query executed successfully ({row_count} rows in {elapsed:.3f}s).")
        except Exception as exc:
            result_columns = []
            result_rows = []
            row_count = 0
            error = str(exc)
            executed_at = timezone.now()
            elapsed = 0
            messages.error(request, f"Query error: {exc}")

        from apps.db_query_history.models import QueryHistory
        QueryHistory.objects.create(
            user=request.user,
            connection=conn_obj,
            query=sql,
            query_type=sql.strip().split()[0].upper() if sql.strip() else "other",
            success=error is None,
            execution_time=elapsed,
            affected_rows=row_count,
            result_columns=result_columns,
            result_preview=result_rows[:100],
            error_message=error or "",
            has_data=row_count > 0,
            row_count=row_count,
        )

        connections = DatabaseConnection.objects.filter(user=request.user, is_active=True)
        return render(request, "connections/execute_query.html", {
            "connection": conn_obj,
            "connections": connections,
            "executed_at": executed_at,
            "error": error,
            "result_columns": result_columns,
            "result_rows": result_rows,
            "row_count": row_count,
            "execution_time": elapsed,
            "sql": sql,
        })


class ExecutingAjaxView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        return redirect("connections:execute")


class CloneConnectionView(LoginRequiredMixin, TemplateView):
    def post(self, request, pk):
        src = get_object_or_404(DatabaseConnection, pk=pk, user=request.user)
        clone = DatabaseConnection.objects.create(
            user=request.user,
            name=f"{src.name} (copy)",
            engine=src.engine,
            host=src.host,
            port=src.port,
            dbname=src.dbname,
            username=src.username,
            password=src.password,
            options=src.options,
        )
        messages.success(request, f"Connection '{clone.name}' created.")
        return redirect("connections:detail", pk=clone.pk)


class ExecuteQueryAjaxView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        return redirect("connections:execute")
