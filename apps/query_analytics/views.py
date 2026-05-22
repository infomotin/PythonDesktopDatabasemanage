"""Main views for the Query Analytics & Performance Monitoring module."""

import json, time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, View, ListView, DetailView
from django.db.models import Count, Avg, F, Max, Q, Sum

from apps.query_analytics.models import (
    QueryExecutionMetric, QueryHistoryEntry, IndexRecommendation,
    SlowQueryAlert, QueryPlanCache, ResourceSnapshot, QueryPattern,
    AIOptimizationSuggestion, PerformanceComparison, QueryReplayRecord,
)
from apps.query_analytics.services.index_recommender import generate_recommendations
from apps.query_analytics.services.ai_optimizer import analyse_query, bulk_analyse
from apps.query_analytics.services.query_replay import compare_engines, replay_query
from apps.subscription.models import Subscription


TIER_LIMITS = {
    "free":         {"ai_suggestions": False, "plan_comparison": False, "realtime": False, "retention_days": 7},
    "premium":      {"ai_suggestions": True,  "plan_comparison": True,  "realtime": True,  "retention_days": 90},
    "enterprise":   {"ai_suggestions": True,  "plan_comparison": True,  "realtime": True,  "retention_days": -1},
}

_TIER_NAMES = {"free": "free", "premium": "pro", "enterprise": "enterprise"}


def _get_tier(request):
    try:
        sub = request.user.subscription
        tier_name = getattr(sub.tier, "name", "free")
        return _TIER_NAMES.get(tier_name, "free")
    except Exception:
        return "free"


def _has_feature(request, feature: str) -> bool:
    return TIER_LIMITS.get(_get_tier(request), {}).get(feature, False)


def _retention_days(request) -> int:
    return TIER_LIMITS.get(_get_tier(request), {}).get("retention_days", 7)


# ── dashboard ──────────────────────────────────────────────────────────────────

class AnalyticsDashboard(LoginRequiredMixin, TemplateView):
    template_name = "query_analytics/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tier = _get_tier(self.request)
        days = _retention_days(self.request)
        qs = QueryExecutionMetric.objects.filter(user=self.request.user)
        if days > 0:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))

        total = qs.count()
        avg_dur = qs.aggregate(Avg("duration_ms"))["duration_ms"] or 0
        slow_qs = qs.filter(duration_ms__gte=500)
        slow_count = slow_qs.count()
        slow_pct = round(slow_count / total * 100, 1) if total else 0
        engine_stats = list(
            qs.values("database_engine").annotate(
                count=Count("id"), avg=Avg("duration_ms"),
                max_dur=Max("duration_ms"),
            ).order_by("-count")[:10]
        )

        latest_resources = ResourceSnapshot.objects.filter(
            user=self.request.user
        ).order_by("-created_at").first()

        ctx.update({
            "page_title": "Query Analytics Dashboard",
            "tier": tier,
            "total_queries": total,
            "avg_duration_ms": round(avg_dur, 1),
            "slow_query_count": slow_count,
            "slow_query_pct": slow_pct,
            "engine_stats": engine_stats,
            "latest_snapshot": latest_resources,
            "has_realtime": _has_feature(self.request, "realtime"),
            "has_ai": _has_feature(self.request, "ai_suggestions"),
            "has_comparison": _has_feature(self.request, "plan_comparison"),
        })
        return ctx


# ── live metrics ───────────────────────────────────────────────────────────────

class MetricsLiveView(LoginRequiredMixin, TemplateView):
    template_name = "query_analytics/metrics_live.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days = _retention_days(self.request)
        qs = QueryExecutionMetric.objects.filter(user=self.request.user)
        if days > 0:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
        ctx["page_title"] = "Live Query Metrics"
        return ctx


# ── recommendations ────────────────────────────────────────────────────────────

class RecommendationsView(LoginRequiredMixin, ListView):
    template_name = "query_analytics/recommendations.html"
    context_object_name = "recommendations"

    def get_queryset(self):
        return IndexRecommendation.objects.filter(
            user=self.request.user
        ).select_related("connection")[:200]


class AnalyzeQueryAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode())
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        sql = body.get("sql", "")
        engine = body.get("engine", "mysql")
        if not sql:
            return JsonResponse({"error": "SQL is required"}, status=400)

        suggestions = analyse_query(request.user, sql.strip(), engine)
        result = [{
            "type": s.suggestion_type,
            "title": s.title,
            "rationale": s.rationale,
            "estimated_improvement_pct": s.estimated_improvement_pct,
            "confidence": s.confidence_score,
            "optimized_sql": s.optimized_sql,
        } for s in suggestions]
        return JsonResponse({"suggestions": result})


class RecommendationsAPI(LoginRequiredMixin, View):
    def get(self, request):
        qs = IndexRecommendation.objects.filter(
            user=request.user
        ).order_by("-created_at")[:100]
        data = [{
            "id": str(r.id), "table": r.table_name, "columns": r.column_names,
            "index_type": r.index_type, "engine": r.database_engine,
            "priority": r.priority, "score": r.score,
            "estimated_improvement_pct": r.estimated_improvement_pct,
            "status": r.status, "ddl": r.suggested_ddl,
            "rationale": r.rationale, "created_at": r.created_at.isoformat(),
        } for r in qs]
        return JsonResponse({"recommendations": data})


# ── execution plans ─────────────────────────────────────────────────────────────

class ExecutionPlansView(LoginRequiredMixin, TemplateView):
    template_name = "query_analytics/execution_plans.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Execution Plans"
        ctx["cached_plans"] = QueryPlanCache.objects.filter(
            connection__user=self.request.user
        ).order_by("-last_used_at")[:50]
        return ctx


class QueryPlanAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode())
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        sql = body.get("sql", "")
        engine = body.get("engine", "mysql")
        conn_id = body.get("connection_id")
        if not sql or not conn_id:
            return JsonResponse({"error": "sql and connection_id required"}, status=400)

        from apps.connections.models import DatabaseConnection
        conn = get_object_or_404(DatabaseConnection, pk=conn_id, user=request.user)
        fp = None
        try:
            import hashlib
            fp = hashlib.sha256(" ".join(sql.strip().split()).encode()).hexdigest()[:32]
            cached = QueryPlanCache.objects.get(query_fingerprint=fp, connection=conn)
            return JsonResponse({"cached": True, "plan": cached.plan_raw, "summary": cached.plan_summary})
        except QueryPlanCache.DoesNotExist:
            pass
        except Exception:
            pass

        from apps.query_analytics.services.metric_collector import _engine_plan_prefix, _capture_plan
        from apps.connections.utils import ConnectionPool
        from apps.core.crypto import decrypt_credential

        pwd = decrypt_credential(conn.password)
        alias = ConnectionPool.get(conn)

        plan_raw = {}
        try:
            # simplified — use metric_collector helper
            from apps.query_analytics.services.metric_collector import collect_metrics
            r = collect_metrics(request.user, conn, sql, take_snapshot=False)
            plan_raw = r.get("execution_plan", {})
        except Exception as exc:
            plan_raw = {"error": str(exc)}

        summary = json.dumps(plan_raw, default=str)[:500]
        if fp:
            QueryPlanCache.objects.update_or_create(
                query_fingerprint=fp, connection=conn,
                defaults={"database_engine": conn.engine, "plan_raw": plan_raw,
                          "plan_summary": summary},
            )
        return JsonResponse({"cached": False, "plan": plan_raw, "summary": summary})


# ── query replay ───────────────────────────────────────────────────────────────

class QueryReplayView(LoginRequiredMixin, DetailView):
    model = QueryExecutionMetric
    template_name = "query_analytics/replay.html"
    context_object_name = "original"

    def get_queryset(self):
        return QueryExecutionMetric.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["replays"] = self.object.replays.all().order_by("-replayed_at")[:20]
        return ctx


class ReplayQueryAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode())
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        metric_id = body.get("metric_id")
        if not metric_id:
            return JsonResponse({"error": "metric_id required"}, status=400)
        metric = get_object_or_404(QueryExecutionMetric, pk=metric_id, user=request.user)
        params = body.get("params", {})
        try:
            record = replay_query(request.user, metric, modified_params=params)
            return JsonResponse({
                "replay_id": str(record.id), "duration_ms": record.duration_ms,
                "rows_affected": record.rows_affected, "rows_returned": record.rows_returned,
                "status": record.status, "error": record.error_message,
            })
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


# ── performance comparison ─────────────────────────────────────────────────────

class PerformanceComparisonView(LoginRequiredMixin, TemplateView):
    template_name = "query_analytics/comparison.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Performance Comparison"
        ctx["comparisons"] = PerformanceComparison.objects.filter(
            user=self.request.user
        ).order_by("-created_at")[:50]
        ctx["available_engines"] = [
            ("mysql", "MySQL"), ("postgresql", "PostgreSQL"), ("mongodb", "MongoDB"),
            ("oracle", "Oracle"), ("sqlite", "SQLite"),
        ]
        return ctx


class PerformanceComparisonAPI(LoginRequiredMixin, View):
    def post(self, request):
        try:
            body = json.loads(request.body.decode())
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")
        sql = body.get("sql", "")
        engine_a = body.get("engine_a")
        engine_b = body.get("engine_b")
        conn_a_id = body.get("connection_a")
        conn_b_id = body.get("connection_b")
        if not sql or not engine_a or not engine_b:
            return JsonResponse({"error": "sql, engine_a and engine_b required"}, status=400)

        conn_a = conn_b = None
        from apps.connections.models import DatabaseConnection
        if conn_a_id:
            conn_a = get_object_or_404(DatabaseConnection, pk=conn_a_id, user=request.user)
        if conn_b_id:
            conn_b = get_object_or_404(DatabaseConnection, pk=conn_b_id, user=request.user)

        try:
            comparison = compare_engines(request.user, sql, engine_a, engine_b,
                                          connection_a=conn_a, connection_b=conn_b)
            return JsonResponse({
                "id": str(comparison.id),
                "engine_a": engine_a, "duration_a_ms": comparison.duration_a_ms,
                "engine_b": engine_b, "duration_b_ms": comparison.duration_b_ms,
                "winner": comparison.winner, "delta_pct": comparison.delta_pct,
            })
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)


# ── slow queries ───────────────────────────────────────────────────────────────

class SlowQueriesView(LoginRequiredMixin, ListView):
    template_name = "query_analytics/slow_queries.html"
    context_object_name = "metrics"

    def get_queryset(self):
        qs = QueryExecutionMetric.objects.filter(
            user=self.request.user, duration_ms__gte=500
        ).order_by("-duration_ms")[:100]
        return qs


class SlowQueriesAPI(LoginRequiredMixin, View):
    def get(self, request):
        threshold = int(request.GET.get("threshold_ms", 500))
        qs = QueryExecutionMetric.objects.filter(
            user=request.user, duration_ms__gte=threshold
        ).order_by("-duration_ms")[:200]
        data = [{
            "id": str(m.id), "sql": m.raw_sql[:200], "query_type": m.query_type,
            "duration_ms": m.duration_ms, "database_engine": m.database_engine,
            "created_at": m.created_at.isoformat(),
        } for m in qs]
        return JsonResponse({"slow_queries": data})


# ── resource snapshot _api ─────────────────────────────────────────────────────

class ResourceSnapshotAPI(LoginRequiredMixin, View):
    def get(self, request):
        conn_id = request.GET.get("connection_id")
        qs = ResourceSnapshot.objects.filter(user=request.user)
        if conn_id:
            qs = qs.filter(connection_id=conn_id)
        qs = qs.order_by("-created_at")[:200]
        data = [{
            "id": str(s.id),
            "pool_usage_pct": s.pool_usage_pct,
            "cpu_usage_pct": s.cpu_usage_pct,
            "memory_mb_used": s.memory_mb_used,
            "active_connections": s.active_connections,
            "idle_connections": s.idle_connections,
            "has_bottleneck": s.has_bottleneck,
            "bottleneck_reason": s.bottleneck_reason,
            "created_at": s.created_at.isoformat(),
        } for s in qs]
        return JsonResponse({"snapshots": data})


# ── metrics aggregated _api ────────────────────────────────────────────────────

class MetricsAPI(LoginRequiredMixin, View):
    def get(self, request):
        days = int(request.GET.get("days", 7))
        engine = request.GET.get("engine", "")
        tier = _get_tier(request)
        days = min(days, _retention_days(request))
        cutoff = timezone.now() - timedelta(days=days)
        qs = QueryExecutionMetric.objects.filter(user=request.user, created_at__gte=cutoff)
        if engine:
            qs = qs.filter(database_engine=engine)
        engine_daily = list(
            qs.extra(select={"d": "date(created_at)"})
            .values("d").annotate(count=Count("id"), avg_dur=Avg("duration_ms")).order_by("d")
        )

        alert_qs = SlowQueryAlert.objects.filter(metric__user=request.user)

        data = {
            "tier": tier,
            "total": qs.count(),
            "avg_duration_ms": round(qs.aggregate(Avg("duration_ms"))["duration_ms"] or 0, 2),
            "p95_duration_ms": round(
                sorted([m.duration_ms for m in qs])[int(len(qs) * 0.95)] if qs.exists() else 0,
                2,
            ),
            "slow_count": qs.filter(duration_ms__gte=500).count(),
            "error_count": qs.filter(status="error").count(),
            "total_memory_mb": round(qs.aggregate(models.Sum("memory_mb"))["memory_mb__sum"] or 0, 2),
            "engine_daily": engine_daily,
            "unread_alerts": alert_qs.filter(is_read=False).count(),
            "query_types": list(
                qs.values("query_type").annotate(count=Count("id")).order_by("-count")
            ),
        }
        return JsonResponse(data)
