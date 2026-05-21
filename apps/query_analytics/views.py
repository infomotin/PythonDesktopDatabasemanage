"""
query_analytics.views
---------------------
All public-facing views and REST / AJAX API views for the analytics dashboard.
Layer:
  * TemplateView / ListView → rendered HTML pages
  * View subclasses         → JSON API endpoints
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import connection as dj_conn, models
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.http import (
    Http404, HttpResponse, JsonResponse, StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView

from apps.connections.models import DatabaseConnection
from apps.db_query_history.models import QueryHistory
from apps.query_analytics.engines.metric_collector    import record_metric
from apps.query_analytics.engines.index_engine        import generate_recommendations
from apps.query_analytics.engines.optimization_engine import generate_suggestions
from apps.query_analytics.engines.plan_parser         import to_json
from apps.query_analytics.engines.slow_query_engine   import check_threshold
from apps.query_analytics.engines.alert_engine        import check_bottlenecks
from apps.query_analytics.models import (
    ConnectionSnapshot, IndexRecommendation, MetricAggregate,
    PerformanceAlert, QueryComparison, QueryExecutionPlan,
    QueryLabel, QueryMetric, QueryOptimizationSuggestion, SlowQuery,
    SqlEngine, AlertPriority,
)
from apps.query_analytics.engines.slow_query_engine import check_threshold

User = get_user_model()

# How many seconds of "live" data to include in the realtime endpoint
REALTIME_WINDOW_SECONDS: int = int(getattr(settings, "QA_REALTIME_WINDOW_SECONDS", 300))


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _tier_gate(request, feature: str):
    """Return True if the current user can access the given analytics feature."""
    try:
        sub = request.user.subscription_ref
    except Exception:
        return feature in ("query_builder", "analytics")
    if not sub or not sub.tier:
        return feature in ("query_builder", "analytics")
    return bool(getattr(sub.tier, f"allow_{feature}", False))


def _to_engine_qs(qs, engine: str):
    return qs.filter(connection__engine=engine) if engine else qs


def _paged(qs, request, per_page=25):
    page = request.GET.get("page", 1)
    paginator = Paginator(qs, per_page)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


# ─────────────────────────────────────────────────────────────────
# BASE MIXIN
# ─────────────────────────────────────────────────────────────────
class AnalyticsRequiredMixin(LoginRequiredMixin):
    """Ensures the subscription tier allows analytics."""

    def dispatch(self, request, *args, **kwargs):
        if not _tier_gate(request, "analytics"):
            messages.error(request, "Analytics is not available on your current plan.")
            return redirect("subscription:pricing")
        return super().dispatch(request, *args, **kwargs)


# ═════════════════════════════════════════════════════════════════
# 1.  DASHBOARD  ──  query_analytics:dashboard
# ═════════════════════════════════════════════════════════════════
class DashboardView(AnalyticsRequiredMixin, TemplateView):
    template_name = "query_analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        now  = timezone.now()

        # ── summary buckets ────────────────────────────────────────
        since_1h  = now - datetime.timedelta(hours=1)
        since_24h = now - datetime.timedelta(hours=24)
        since_7d  = now - datetime.timedelta(days=7)

        qm = QueryMetric.objects.filter(user=u)

        def agg(qs):
            a = qs.aggregate(
                count   = Count("id"),
                avg_dur = Avg("duration_ms"),
                max_dur = Max("duration_ms"),
                rows    = Sum("rows_affected"),
                slow    = Count("id", filter=Q(is_slow=True)),
                errors  = Count("id", filter=Q(status="error")),
            )
            return {k: (v or 0) for k, v in a.items()}

        ctx["sum_1h"]  = agg(qm.filter(executed_at__gte=since_1h))
        ctx["sum_24h"] = agg(qm.filter(executed_at__gte=since_24h))
        ctx["sum_7d"]  = agg(qm.filter(executed_at__gte=since_7d))
        ctx["all_time"] = agg(qm)

        # ── engine breakdown ───────────────────────────────────────
        ctx["engine_stats"] = (
            qm.values("engine")
            .annotate(
                count   = Count("id"),
                avg_dur = Avg("duration_ms"),
                slow    = Count("id", filter=Q(is_slow=True)),
            )
            .order_by("-count")[:10]
        )

        # ── recent slow queries ────────────────────────────────────
        ctx["recent_slow"] = SlowQuery.objects.filter(
            user=u, status=SlowQuery.ACTIVE
        ).order_by("-last_seen")[:10]

        # ── open alerts ───────────────────────────────────────────
        ctx["open_alerts"] = PerformanceAlert.objects.filter(
            user=u, resolved=False
        ).order_by("-created_at")[:10]

        # ── top recommendations ────────────────────────────────────
        ctx["top_recs"] = IndexRecommendation.objects.filter(
            user=u, status=IndexRecommendation.PENDING,
        ).order_by("-score")[:5]

        # ── connection list for selector ───────────────────────────
        ctx["connections"] = DatabaseConnection.objects.filter(
            user=u, is_active=True
        ).order_by("name")

        # ── subscriptions feature gate ─────────────────────────────
        tier = getattr(u.subscription_ref.tier if hasattr(u, "subscription_ref") else None, "name", "free")
        ctx["tier"]         = tier
        has_premium        = tier in ("pro", "enterprise")
        ctx["has_premium"]  = has_premium
        ctx["is_enterprise"] = tier == "enterprise"

        return ctx


# ═════════════════════════════════════════════════════════════════
# 2.  METRIC LIST  ──  query_analytics:metrics
# ═════════════════════════════════════════════════════════════════
class MetricListView(AnalyticsRequiredMixin, ListView):
    template_name = "query_analytics/metrics.html"
    context_object_name = "metrics"
    paginate_by = 50

    def get_queryset(self):
        qs = QueryMetric.objects.filter(user=self.request.user).select_related(
            "connection", "query_history", "execution_plan",
        )
        engine   = self.request.GET.get("engine")
        status   = self.request.GET.get("status")
        slow     = self.request.GET.get("slow")
        conn_id  = self.request.GET.get("connection_id")
        q        = self.request.GET.get("q")
        if engine:
            qs = qs.filter(engine=engine)
        if status:
            qs = qs.filter(status=status)
        if slow == "1":
            qs = qs.filter(is_slow=True)
        if conn_id:
            qs = qs.filter(connection_id=conn_id)
        if q:
            qs = qs.filter(Q(query_text__icontains=q) | Q(query_label__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["connections"] = DatabaseConnection.objects.filter(
            user=self.request.user
        ).values_list("id", "name", "engine")
        ctx["engines"] = SqlEngine.choices
        ctx["statuses"] = MetricStatus.choices
        ctx["selected_engine"]   = self.request.GET.get("engine", "")
        ctx["selected_status"]   = self.request.GET.get("status", "")
        ctx["selected_conn"]     = self.request.GET.get("connection_id", "")
        ctx["search_q"]          = self.request.GET.get("q", "")
        ctx["slow_only"]         = self.request.GET.get("slow") == "1"
        return ctx


# ═════════════════════════════════════════════════════════════════
# 3.  LIVE METRICS STREAM  (SSE  →  query_analytics:metrics_stream)
# ═════════════════════════════════════════════════════════════════
class MetricsStreamView(AnalyticsRequiredMixin, View):
    """
    Server-Sent Events endpoint.

    Each frame is a JSON blob with the latest metric rows so that the
    front-end JS can append them to the live table without a full reload.
    """

    def get(self, request):
        u = request.user
        window = REALTIME_WINDOW_SECONDS
        cutoff = timezone.now() - datetime.timedelta(seconds=window)

        qs = QueryMetric.objects.filter(
            user=u, executed_at__gte=cutoff,
        ).select_related("connection").order_by("-executed_at")

        engine = request.GET.get("engine")
        if engine:
            qs = qs.filter(engine=engine)

        data = [
            {
                "id": str(m.id),
                "engine":  m.engine,
                "label":   m.query_label,
                "text":    m.query_text[:120],
                "duration_ms": m.duration_ms,
                "rows_affected": m.rows_affected,
                "memory_mb": m.memory_consumed_mb,
                "cpu_pct": m.cpu_percent,
                "status":  m.status,
                "is_slow": m.is_slow,
                "executed_at": m.executed_at.strftime("%H:%M:%S"),
            }
            for m in qs[:200]
        ]
        return JsonResponse({
            "window_seconds": window,
            "count": len(data),
            "metrics": data,
        })


# ═════════════════════════════════════════════════════════════════
# 4.  QUERY HISTORY  ──  query_analytics:history
# ═════════════════════════════════════════════════════════════════
class QueryHistoryView(AnalyticsRequiredMixin, TemplateView):
    template_name = "query_analytics/history.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u  = self.request.user
        qs = QueryMetric.objects.filter(user=u).select_related("connection")

        engine  = self.request.GET.get("engine")
        week    = self.request.GET.get("period", "7")
        q       = self.request.GET.get("q")
        if engine:
            qs = qs.filter(engine=engine)
        if week != "all":
            cutoff = timezone.now() - datetime.timedelta(days=int(week))
            qs = qs.filter(executed_at__gte=cutoff)
        if q:
            qs = qs.filter(Q(query_text__icontains=q) | Q(query_label__icontains=q))

        ctx["periods"] = [("1", "24h"), ("7", "7d"), ("30", "30d"), ("90", "90d"), ("all", "All")]
        ctx["selected_period"] = week
        ctx["metrics"]     = _paged(qs, self.request)
        ctx["total_count"] = qs.count()
        ctx["engines"]     = SqlEngine.choices
        ctx["search_q"]    = q or ""
        return ctx


class QueryHistoryDetailView(AnalyticsRequiredMixin, DetailView):
    template_name = "query_analytics/history_detail.html"
    context_object_name = "metric"
    model = QueryMetric
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return QueryMetric.objects.filter(
            user=self.request.user
        ).select_related("connection", "execution_plan", "query_history")


class QueryReplayView(AnalyticsRequiredMixin, View):
    """Re-runs a historical query on its original connection and records results."""

    def post(self, request, pk):
        metric = get_object_or_404(QueryMetric, pk=pk, user=request.user)
        if not metric.connection:
            messages.error(request, "No connection associated with this metric.")
            return redirect("query_analytics:history_detail", pk=pk)

        pwd = decrypt_credential(metric.connection.password)
        sql = metric.query_history.query if metric.query_history_id else metric.query_text[:4000]

        engine = metric.connection.engine
        try:
            from apps.core.adapters.factory import EngineFactory
            adapter = EngineFactory.create(
                engine, metric.connection.host, metric.connection.port,
                metric.connection.dbname, metric.connection.username, pwd,
            )
        except Exception:
            messages.error(request, "Engine adapter unavailable.")
            return redirect("query_analytics:history_detail", pk=pk)

        try:
            t0   = timezone.now()
            cols, rows = adapter.execute(sql)
            elapsed_s = (timezone.now() - t0).total_seconds()
            mem  = record_metric.__module__ if False else 0
            record_metric(
                user=request.user,
                engine=engine,
                query_text=sql[:2000],
                duration_ms=elapsed_s * 1000,
                rows_affected=len(rows),
                connection=metric.connection,
                success=True,
            )
            messages.success(request,
                             f"Replay returned {len(rows)} rows in {elapsed_s:.3f}s.")
        except Exception as exc:
            record_metric(
                user=request.user,
                engine=engine,
                query_text=sql[:2000],
                duration_ms=0,
                connection=metric.connection,
                success=False,
                error_message=str(exc),
            )
            messages.error(request, f"Replay failed: {exc}")
        return redirect("query_analytics:history_detail", pk=pk)


# ═════════════════════════════════════════════════════════════════
# 5.  SLOW QUERIES  ──  query_analytics:slow_queries
# ═════════════════════════════════════════════════════════════════
class SlowQueryListView(AnalyticsRequiredMixin, ListView):
    template_name   = "query_analytics/slow_queries.html"
    context_object_name = "slow_queries"
    paginate_by     = 25

    def get_queryset(self):
        return SlowQuery.objects.filter(
            user=self.request.user,
        ).select_related("connection").order_by("-last_seen")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        ctx["total_count"] = qs.count()
        ctx["active_count"] = qs.filter(status=SlowQuery.ACTIVE).count()
        return ctx


class SlowQueryDetailView(AnalyticsRequiredMixin, DetailView):
    template_name   = "query_analytics/slow_query_detail.html"
    context_object_name = "slow_query"
    model           = SlowQuery
    pk_url_kwarg    = "pk"

    def get_queryset(self):
        return SlowQuery.objects.filter(
            user=self.request.user,
        ).prefetch_related("recommendations", "metrics")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sq = self.object
        ctx["recent_metrics"] = sq.metrics.all().order_by("-executed_at")[:20]
        ctx["recommendations"] = sq.recommendations.filter(
            user=self.request.user,
        ).order_by("-score")
        return ctx


# ═════════════════════════════════════════════════════════════════
# 6.  INDEX RECOMMENDATIONS  ──  query_analytics:recommendations
# ═════════════════════════════════════════════════════════════════
class RecommendationListView(AnalyticsRequiredMixin, ListView):
    template_name         = "query_analytics/recommendations.html"
    context_object_name   = "recommendations"
    paginate_by           = 20

    def get_queryset(self):
        qs = IndexRecommendation.objects.filter(
            user=self.request.user,
        ).select_related("connection").order_by("-score", "-created_at")
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = RecommendationStatus.choices
        ctx["selected_status"] = self.request.GET.get("status", "")
        # Run the engine on GET if requested
        if self.request.GET.get("run") == "1":
            new_recs = generate_recommendations(str(self.request.user.id))
            messages.success(self.request, f"Generated {len(new_recs)} new recommendations.")
        return ctx


class RecommendationDetailView(AnalyticsRequiredMixin, DetailView):
    template_name       = "query_analytics/recommendation_detail.html"
    context_object_name = "rec"
    model               = IndexRecommendation
    pk_url_kwarg        = "pk"

    def get_queryset(self):
        return IndexRecommendation.objects.filter(user=self.request.user)


class RecommendationDismissView(AnalyticsRequiredMixin, View):
    def post(self, request, pk):
        rec = get_object_or_404(IndexRecommendation, pk=pk, user=request.user)
        reason = request.POST.get("reason", "dismissed by user")
        rec.status     = RecommendationStatus.DISMISSED
        rec.dismissed_at  = timezone.now()
        rec.dismissed_reason = reason
        rec.save(update_fields=["status", "dismissed_at", "dismissed_reason"])
        messages.info(request, "Recommendation dismissed.")
        return redirect("query_analytics:recommendation_detail", pk=pk)


class RecommendationApplyView(AnalyticsRequiredMixin, View):
    def post(self, request, pk):
        rec = get_object_or_404(IndexRecommendation, pk=pk, user=request.user)
        # We don’t execute the DDL here — that’s an admin action.
        rec.status    = RecommendationStatus.APPLIED
        rec.applied_at = timezone.now()
        rec.save(update_fields=["status", "applied_at"])
        messages.success(request, "Recommendation marked as applied.")
        return redirect("query_analytics:recommendation_detail", pk=pk)


# ═════════════════════════════════════════════════════════════════
# 7.  OPTIMIZATION SUGGESTIONS  ──  query_analytics:optimizations
# ═════════════════════════════════════════════════════════════════
class OptimizationSuggestionListView(AnalyticsRequiredMixin, ListView):
    template_name         = "query_analytics/optimizations.html"
    context_object_name   = "suggestions"
    paginate_by           = 20

    def get_queryset(self):
        qs = QueryOptimizationSuggestion.objects.filter(
            user=self.request.user,
        ).select_related("query_metric", "slow_query", "execution_plan").order_by(
            "-estimated_improvement_pct", "-created_at"
        )
        engine = self.request.GET.get("engine")
        if engine:
            qs = qs.filter(engine=engine)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["engines"] = SqlEngine.choices
        # Run generator on demand
        if self.request.GET.get("run") == "1":
            new_sugs = generate_suggestions(str(self.request.user.id))
            messages.success(self.request, f"Analysed queries and added {len(new_sugs)} suggestions.")
        return ctx


# ═════════════════════════════════════════════════════════════════
# 8.  QUERY COMPARISON  ──  query_analytics:compare
# ═════════════════════════════════════════════════════════════════
class QueryCompareView(AnalyticsRequiredMixin, TemplateView):
    template_name = "query_analytics/compare.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u   = self.request.user
        ctx["connections"] = DatabaseConnection.objects.filter(
            user=u, is_active=True
        ).order_by("name")
        return ctx


class QueryCompareDetailView(AnalyticsRequiredMixin, DetailView):
    template_name       = "query_analytics/compare_detail.html"
    context_object_name = "comp"
    model               = QueryComparison
    pk_url_kwarg        = "pk"

    def get_queryset(self):
        return QueryComparison.objects.filter(
            user=self.request.user,
        ).prefetch_related("metrics")


# ═════════════════════════════════════════════════════════════════
# 9.  PERFORMANCE ALERTS  ──  query_analytics:alerts
# ═════════════════════════════════════════════════════════════════
class PerformanceAlertListView(AnalyticsRequiredMixin, ListView):
    template_name         = "query_analytics/alerts.html"
    context_object_name   = "alerts"
    paginate_by           = 25

    def get_queryset(self):
        qs = PerformanceAlert.objects.filter(
            user=self.request.user,
        ).select_related("connection").order_by("-created_at")
        resolved = self.request.GET.get("resolved")
        if resolved == "1":
            qs = qs.filter(resolved=True)
        elif resolved == "0":
            qs = qs.filter(resolved=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_resolved"] = self.request.GET.get("resolved", "")
        return ctx


class AlertAcknowledgeView(AnalyticsRequiredMixin, View):
    def post(self, request, pk):
        alert = get_object_or_404(PerformanceAlert, pk=pk, user=request.user)
        alert.acknowledge()
        messages.info(request, "Alert acknowledged.")
        return redirect("query_analytics:alerts")


# ═════════════════════════════════════════════════════════════════
# 10. RESOURCE MONITOR  ──  query_analytics:resources
# ═════════════════════════════════════════════════════════════════
class ResourceMonitorView(AnalyticsRequiredMixin, TemplateView):
    template_name = "query_analytics/resources.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u   = self.request.user

        conn_ids = DatabaseConnection.objects.filter(
            user=u, is_active=True
        ).values_list("id", flat=True)

        # Latest pool snapshot per connection
        snapshots = (
            ConnectionSnapshot.objects.filter(connection_id__in=conn_ids)
            .select_related("connection")
            .order_by("-timestamp")
        )
        latest_map = {}
        for snap in snapshots:
            if str(snap.connection_id) not in latest_map:
                latest_map[str(snap.connection_id)] = snap
        ctx["pool_snapshots"] = list(latest_map.values())

        # Last 1h connection count timeline
        since = timezone.now() - datetime.timedelta(hours=24)
        ctx["timeline_data"] = (
            MetricAggregate.objects.filter(
                user=u, granularity="15m", bucket_start__gte=since,
            ).order_by("bucket_start").values(
                "engine", "bucket_start", "query_count",
                "avg_duration_ms", "avg_cpu_pct", "avg_memory_mb",
            )
        )

        ctx["connections"] = DatabaseConnection.objects.filter(
            user=u, is_active=True,
        ).order_by("name")
        return ctx


# ═════════════════════════════════════════════════════════════════
# 11.  REST API  ─────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════

class LiveMetricsAPIView(AnalyticsRequiredMixin, View):
    """Returns the most-recent metrics for the live dashboard table."""

    def get(self, request):
        u     = request.user
        secs  = int(request.GET.get("window", REALTIME_WINDOW_SECONDS))
        cutoff = timezone.now() - datetime.timedelta(seconds=secs)
        engine = request.GET.get("engine")
        qs = QueryMetric.objects.filter(
            user=u, executed_at__gte=cutoff,
        ).select_related("connection").order_by("-executed_at")
        if engine:
            qs = qs.filter(engine=engine)
        records = [
            {
                "id": str(m.id),
                "engine": m.engine,
                "duration_ms": m.duration_ms,
                "rows_affected": m.rows_affected,
                "memory_mb": m.memory_consumed_mb,
                "cpu_pct": m.cpu_percent,
                "status": m.status,
                "is_slow": m.is_slow,
                "connection_name": m.connection.name if m.connection else "—",
                "executed_at": m.executed_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for m in qs[:500]
        ]
        return JsonResponse({"count": len(records), "metrics": records,
                             "window_seconds": secs})


class MetricsSummaryAPIView(AnalyticsRequiredMixin, View):
    """Aggregate KPIs split by engine and time-range for dashboard cards."""

    def get(self, request):
        u       = request.user
        period  = request.GET.get("period", "1h")
        now     = timezone.now()
        windows = {
            "5m": datetime.timedelta(minutes=5),
            "15m": datetime.timedelta(minutes=15),
            "1h": datetime.timedelta(hours=1),
            "6h": datetime.timedelta(hours=6),
            "24h": datetime.timedelta(hours=24),
            "7d": datetime.timedelta(days=7),
        }
        delta = windows.get(period, datetime.timedelta(hours=1))
        since = now - delta

        qs = QueryMetric.objects.filter(user=u, executed_at__gte=since)
        agg = qs.aggregate(
            total_queries = Count("id"),
            avg_dur       = Avg("duration_ms"),
            max_dur       = Max("duration_ms"),
            total_rows    = Sum("rows_affected"),
            slow_count    = Count("id", filter=Q(is_slow=True)),
            error_count   = Count("id", filter=Q(status="error")),
            total_mem_mb  = Sum("memory_consumed_mb"),
            avg_cpu       = Avg("cpu_percent"),
        )
        engine_breakdown = list(
            qs.values("engine")
            .annotate(
                count   = Count("id"),
                avg_dur = Avg("duration_ms"),
                slow    = Count("id", filter=Q(is_slow=True)),
            )
            .order_by("-count")
        )
        return JsonResponse({
            "period": period,
            **{k: (round(v, 2) if isinstance(v, float) else (v or 0))
               for k, v in agg.items()},
            "by_engine": engine_breakdown,
        })


class AnalyzeQueryAPIView(AnalyticsRequiredMixin, View):
    """
    API:  POST  /api/analytics/analyze/
    Body: { "query": "...", "engine": "postgresql", "connection_id": "<uuid>" }

    Returns an execution plan (if DB API supports EXPLAIN via Django)
    plus AI-powered optimisation suggestions.
    """
    def post(self, request):
        try:
            body  = json.loads(request.body.decode())
            sql   = body.get("query", "").strip()
            engine = body.get("engine", "")
            conn_id = body.get("connection_id", "")
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        if not sql or not engine:
            return JsonResponse({"error": "query and engine are required"}, status=400)

        user = request.user
        conn = None
        if conn_id:
            try:
                conn = DatabaseConnection.objects.get(
                    id=conn_id, user=user, is_active=True,
                )
            except DatabaseConnection.DoesNotExist:
                return JsonResponse({"error": "Connection not found"}, status=404)

        # fetch execution plan
        plan_text = _fetch_plan(sql, engine, conn)
        plan_json = to_json(plan_text, engine) if plan_text else {}

        # generate suggestions
        metric = QueryMetric(
            user=user,
            connection=conn,
            engine=engine,
            query_text=sql[:4000],
            duration_ms=0,
        )
        sugs = generate_suggestions(
            user_id=str(user.id),
            metric=metric,
            engine=engine,
        )
        suggestion_list = [
            {
                "type":  s.suggestion_type,
                "title": s.title,
                "description": s.description,
                "rationale": s.rationale,
                "estimated_improvement_pct": s.estimated_improvement_pct,
                "confidence": s.confidence,
                "optimized_query": s.optimized_query,
            }
            for s in sugs
        ]
        return JsonResponse({
            "plan_text": plan_text,
            "plan_json": plan_json,
            "suggestions": suggestion_list,
        })


def _fetch_plan(sql: str, engine: str, conn) -> str | None:
    """Best-effort EXPLAIN using the Django operator."""
    if not conn:
        return None
    engine_map = {"postgresql": "EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS)", "mysql": "EXPLAIN", "oracle": "EXPLAIN PLAN FOR"}
    prefix = engine_map.get(engine, "EXPLAIN")
    try:
        with dj_conn.cursor() as cursor:
            cursor.execute(f"{prefix}\n{sql}")
            return "\n".join(r[0] for r in cursor.fetchall())
    except Exception:
        return None


class RecommendationsAPIView(AnalyticsRequiredMixin, View):
    def get(self, request):
        qs  = IndexRecommendation.objects.filter(
            user=request.user, status=IndexRecommendation.PENDING,
        ).select_related("connection").order_by("-score", "-created_at")[:50]
        return JsonResponse({
            "count": qs.count(),
            "items": [
                {
                    "id":                   str(r.id),
                    "table":                r.table_name,
                    "columns":              r.column_names,
                    "index_type":           r.index_type,
                    "score":                r.score,
                    "estimated_improvement_pct": r.estimated_improvement_pct,
                    "create_statement":     r.create_statement,
                    "rationale":            r.rationale,
                    "engine":               r.engine,
                }
                for r in qs
            ],
        })


class AlertAPIView(AnalyticsRequiredMixin, View):
    def get(self, request):
        qs = PerformanceAlert.objects.filter(
            user=request.user,
        ).select_related("connection").order_by("-created_at")[:50]
        return JsonResponse({
            "count": qs.count(),
            "items": [
                {
                    "id":       str(a.id),
                    "type":     a.alert_type,
                    "priority": a.priority,
                    "title":    a.title,
                    "message":  a.message,
                    "resolved": a.resolved,
                    "acknowledged": a.acknowledged,
                    "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for a in qs
            ],
        })


class ExecutionPlanAPIView(AnalyticsRequiredMixin, View):
    def get(self, request, pk):
        plan = get_object_or_404(QueryExecutionPlan, pk=pk)
        return JsonResponse({
            "id":            str(plan.id),
            "engine":        plan.engine,
            "plan_text":     plan.plan_text,
            "parsed_plan":   plan.parsed_plan,
            "total_cost":    plan.total_cost,
            "execution_time_ms": plan.execution_time_ms,
            "rows_examined": plan.rows_examined,
            "rows_returned": plan.rows_returned,
            "indexes_used":  plan.indexes_used,
            "created_at":    plan.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        })


# ═════════════════════════════════════════════════════════════════
# 12.  REPORTS  ─────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════
class ReportView(AnalyticsRequiredMixin, TemplateView):
    template_name = "query_analytics/reports.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u   = self.request.user
        # date range filter
        rng = self.request.GET.get("range", "30")
        cutoff = timezone.now() - datetime.timedelta(days=int(rng) if rng.isdigit() else 30)
        qs = QueryMetric.objects.filter(user=u, executed_at__gte=cutoff)
        ctx["summary"] = qs.aggregate(
            total      = Count("id"),
            avg_dur    = Avg("duration_ms"),
            max_dur    = Max("duration_ms"),
            slow       = Count("id", filter=Q(is_slow=True)),
            errors     = Count("id", filter=Q(status="error")),
            total_rows = Sum("rows_affected"),
        )
        ctx["recs"] = IndexRecommendation.objects.filter(
            user=u, created_at__gte=cutoff,
        ).count()
        ctx["alerts"] = PerformanceAlert.objects.filter(
            user=u, created_at__gte=cutoff,
        ).count()
        ctx["range"] = rng
        return ctx


class ReportExportView(AnalyticsRequiredMixin, View):
    """Stream a CSV of all metrics in the selected time window."""

    def get(self, request):
        rng = request.GET.get("range", "30")
        cutoff = timezone.now() - datetime.timedelta(days=int(rng) if rng.isdigit() else 30)
        qs = QueryMetric.objects.filter(
            user=request.user, executed_at__gte=cutoff,
        ).select_related("connection").order_by("-executed_at")
        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerow(["ID", "Engine", "Status", "Duration ms", "Rows Affected",
                     "Memory MB", "CPU %", "Is Slow", "Connection",
                     "Query Label", "Executed At"])
        for m in qs:
            w.writerow([
                str(m.id), m.engine, m.status, m.duration_ms, m.rows_affected,
                m.memory_consumed_mb, m.cpu_percent, m.is_slow,
                m.connection.name if m.connection else "",
                (m.query_label or m.query_text[:80]).replace("\n", " "),
                m.executed_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        csv_bytes = buf.getvalue().encode("utf-8")
        resp = HttpResponse(csv_bytes, content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="query_analytics_{request.user.id[:8]}_{rng}d.csv"'
        )
        return resp
