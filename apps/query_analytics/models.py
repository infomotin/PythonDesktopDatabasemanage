import uuid
import hashlib

from django.contrib import admin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def _query_fingerprint(sql: str) -> str:
    stripped = " ".join(sql.strip().split())
    return hashlib.sha256(stripped.encode()).hexdigest()[:32]


# ── 1. Query execution metric ─────────────────────────────────────────────────

class QueryExecutionMetric(models.Model):
    STATUS_CHOICES = [
        ("success", _("Success")), ("error", _("Error")), ("timeout", _("Timeout")),
        ("cancelled", _("Cancelled")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_metrics")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True, related_name="query_metrics")
    database = models.ForeignKey("tables.VirtualDatabase", on_delete=models.SET_NULL, null=True, blank=True, related_name="query_metrics")
    raw_sql = models.TextField()
    query_fingerprint = models.CharField(max_length=32, db_index=True)
    params = models.JSONField(default=dict, blank=True)
    duration_ms = models.FloatField(default=0)
    rows_affected = models.BigIntegerField(default=0)
    rows_returned = models.BigIntegerField(default=0)
    memory_mb = models.FloatField(default=0)
    cpu_ms = models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    error_message = models.TextField(blank=True, null=True)
    execution_plan = models.JSONField(default=dict, blank=True)
    # resource utilization
    active_connections = models.IntegerField(default=0)
    idle_connections = models.IntegerField(default=0)
    pool_usage_pct = models.FloatField(default=0)
    query_type = models.CharField(max_length=20, default="SELECT")
    database_engine = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "query_analytics_execution_metric"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["connection", "created_at"]),
            models.Index(fields=["query_fingerprint"]),
            models.Index(fields=["duration_ms"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.query_type} on {self.database_engine} — {self.duration_ms:.1f}ms @ {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self.query_fingerprint:
            self.query_fingerprint = _query_fingerprint(self.raw_sql)
        super().save(*args, **kwargs)

    def is_slow(self) -> bool:
        return self.duration_ms > 500

    def memory_kb(self) -> float:
        return self.memory_mb * 1024


# ── 2. Query history entry ─────────────────────────────────────────────────────

class QueryHistoryEntry(models.Model):
    QUERY_TYPE_CHOICES = [
        ("select", _("SELECT")), ("insert", _("INSERT")), ("update", _("UPDATE")),
        ("delete", _("DELETE")), ("create", _("CREATE")), ("drop", _("DROP")),
        ("alter", _("ALTER")), ("exec", _("EXEC")), ("other", _("OTHER")),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_history_entries")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.SET_NULL, null=True, blank=True, related_name="query_history_entries")
    database = models.ForeignKey("tables.VirtualDatabase", on_delete=models.SET_NULL, null=True, blank=True, related_name="query_history_entries")
    raw_sql = models.TextField()
    query_fingerprint = models.CharField(max_length=32, db_index=True)
    query_type = models.CharField(max_length=20, choices=QUERY_TYPE_CHOICES, default="other")
    params = models.JSONField(default=dict, blank=True)
    duration_ms = models.FloatField(default=0)
    rows_affected = models.BigIntegerField(default=0)
    result_columns = models.JSONField(default=list, blank=True)
    result_preview = models.JSONField(default=list, blank=True)
    result_row_count = models.BigIntegerField(default=0)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    execution_plan = models.JSONField(default=dict, blank=True)
    auto_discovered_schema = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "query_analytics_history_entry"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["connection", "created_at"]),
            models.Index(fields=["query_fingerprint", "duration_ms"]),
        ]

    def __str__(self):
        return f"{self.user.email} — {self.query_type} — {self.created_at:%Y-%m-%d %H:%M}"


# ── 3. Query replay record ────────────────────────────────────────────────────

class QueryReplayRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original = models.ForeignKey(QueryExecutionMetric, on_delete=models.CASCADE, related_name="replays")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_replays")
    replayed_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.FloatField(default=0)
    rows_affected = models.BigIntegerField(default=0)
    rows_returned = models.BigIntegerField(default=0)
    memory_mb = models.FloatField(default=0)
    status = models.CharField(max_length=20, default="success")
    error_message = models.TextField(blank=True, null=True)
    modified_params = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_analytics_replay_record"
        ordering = ["-replayed_at"]

    def __str__(self):
        return f"Replay of {self.original.id} — {self.duration_ms:.1f}ms"


# ── 4. Performance comparison ─────────────────────────────────────────────────

class PerformanceComparison(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="performance_comparisons")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logical_sql = models.TextField()
    param_variants = models.JSONField(default=list, blank=True)
    engine_a = models.CharField(max_length=30)   # e.g. "mysql"
    engine_b = models.CharField(max_length=30)   # e.g. "postgresql"
    # per-engine results
    duration_a_ms = models.FloatField(default=0)
    rows_a = models.BigIntegerField(default=0)
    memory_a_mb = models.FloatField(default=0)
    plan_a = models.JSONField(default=dict, blank=True)
    duration_b_ms = models.FloatField(default=0)
    rows_b = models.BigIntegerField(default=0)
    memory_b_mb = models.FloatField(default=0)
    plan_b = models.JSONField(default=dict, blank=True)
    winner = models.CharField(max_length=30, blank=True)  # engine label of faster result
    delta_pct = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_analytics_performance_comparison"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.engine_a} vs {self.engine_b}"


# ── 5. Index recommendation ───────────────────────────────────────────────────

class IndexRecommendation(models.Model):
    PRIORITY_CHOICES = [("critical", _("Critical")), ("high", _("High")), ("medium", _("Medium")), ("low", _("Low"))]
    STATUS_CHOICES = [("pending", _("Pending")), ("accepted", _("Accepted")), ("rejected", _("Rejected")), ("applied", _("Applied")), ("dismissed", _("Dismissed"))]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="index_recommendations")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True, related_name="index_recommendations")
    database_engine = models.CharField(max_length=30)
    database_name = models.CharField(max_length=255)
    table_name = models.CharField(max_length=255)
    column_names = models.JSONField(default=list, blank=True)
    index_type = models.CharField(max_length=50)           # e.g. "btree", "hash", "gin", "gist"
    suggested_ddl = models.TextField()
    rationale = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    score = models.FloatField(default=0)                   # 0–100
    estimated_improvement_pct = models.FloatField(default=0)
    affected_query_fingerprints = models.JSONField(default=list, blank=True)
    based_on_slow_queries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "query_analytics_index_recommendation"
        ordering = ["-score", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["database_engine", "table_name"]),
        ]

    def __str__(self):
        return f"{self.table_name}.{', '.join(self.column_names)} [{self.priority}] ({self.get_status_display()})"


# ── 6. Slow query alert threshold ─────────────────────────────────────────────

class SlowQueryAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="slow_query_alerts")
    metric = models.ForeignKey(QueryExecutionMetric, on_delete=models.CASCADE, related_name="alerts")
    threshold_ms = models.FloatField(default=500)
    message = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, default="warning",
                                choices=[("critical", "Critical"), ("warning", "Warning"), ("info", "Info")])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_analytics_slow_query_alert"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity}] {self.message}"


# ── 7. Query plan cache ───────────────────────────────────────────────────────

class QueryPlanCache(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query_fingerprint = models.CharField(max_length=32, db_index=True)
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True)
    database_engine = models.CharField(max_length=30)
    plan_raw = models.JSONField(default=dict, blank=True)
    plan_summary = models.TextField()
    estimated_cost = models.FloatField(default=0)
    estimated_rows = models.BigIntegerField(default=0)
    actual_rows = models.BigIntegerField(default=0)
    plan_version = models.CharField(max_length=20, default="1.0")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "query_analytics_query_plan_cache"
        ordering = ["-last_used_at"]
        unique_together = ["query_fingerprint", "connection"]

    def __str__(self):
        return f"Plan cache {self.query_fingerprint[:8]} ({self.database_engine})"


# ── 8. Resource utilization snapshot ─────────────────────────────────────────

class ResourceSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True, blank=True, related_name="resource_snapshots")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True, related_name="resource_snapshots")
    # connection pool
    active_connections = models.IntegerField(default=0)
    idle_connections = models.IntegerField(default=0)
    pool_capacity = models.IntegerField(default=0)
    pool_usage_pct = models.FloatField(default=0)
    # CPU & memory
    cpu_usage_pct = models.FloatField(default=0)
    memory_mb_used = models.FloatField(default=0)
    memory_mb_total = models.FloatField(default=0)
    # currently running top queries
    active_query_count = models.IntegerField(default=0)
    long_running_query_count = models.IntegerField(default=0)
    top_query_fingerprint = models.CharField(max_length=32, blank=True)
    top_query_duration_ms = models.FloatField(default=0)
    # alert-level
    has_bottleneck = models.BooleanField(default=False)
    bottleneck_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "query_analytics_resource_snapshot"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["connection", "created_at"]),
            models.Index(fields=["has_bottleneck"]),
        ]

    def __str__(self):
        tgt = self.connection or self.user or "global"
        return f"Resource snapshot for {tgt} @ {self.created_at:%Y-%m-%d %H:%M}"


# ── 9. Query group / pattern ───────────────────────────────────────────────────

class QueryPattern(models.Model):
    fingerprint = models.CharField(max_length=32, primary_key=True)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="query_patterns")
    connection = models.ForeignKey("connections.DatabaseConnection", on_delete=models.CASCADE, null=True, blank=True, related_name="query_patterns")
    engine = models.CharField(max_length=30, blank=True)
    sample_sql = models.TextField()
    query_type = models.CharField(max_length=20, default="SELECT")
    total_executions = models.BigIntegerField(default=0)
    avg_duration_ms = models.FloatField(default=0)
    min_duration_ms = models.FloatField(default=0)
    max_duration_ms = models.FloatField(default=0)
    p95_duration_ms = models.FloatField(default=0)
    last_executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "query_analytics_query_pattern"
        ordering = ["-p95_duration_ms"]

    def __str__(self):
        return f"Pattern {self.fingerprint[:8]} — avg {self.avg_duration_ms:.1f}ms ({self.total_executions} runs)"


# ── 10. AI optimization suggestion ─────────────────────────────────────────────

class AIOptimizationSuggestion(models.Model):
    SUGGESTION_TYPE_CHOICES = [
        ("missing_index", _("Missing Index")),
        ("unnecessary_join", _("Unnecessary JOIN")),
        ("subquery_extraction", _("Subquery Extraction")),
        ("aggregation_reorder", _("Aggregation Reorder")),
        ("full_table_scan", _("Full Table Scan")),
        ("column_select_star", _("Avoid SELECT *")),
        ("limit_add", _("Add LIMIT")),
        ("batch_insert", _("Batch INSERT")),
        ("other", _("Other")),
    ]
    STATUS_CHOICES = [("pending", _("Pending")), ("applied", _("Applied")), ("dismissed", _("Dismissed"))]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="ai_optimizations")
    metric = models.ForeignKey(QueryExecutionMetric, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_suggestions")
    database_engine = models.CharField(max_length=30)
    original_sql = models.TextField()
    optimized_sql = models.TextField(blank=True)
    suggestion_type = models.CharField(max_length=50, choices=SUGGESTION_TYPE_CHOICES, default="other")
    title = models.CharField(max_length=255)
    rationale = models.TextField()
    estimated_improvement_pct = models.FloatField(default=0)
    confidence_score = models.FloatField(default=0)
    execution_plan_before = models.JSONField(default=dict, blank=True)
    execution_plan_after = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_analytics_ai_suggestion"
        ordering = ["-confidence_score", "-created_at"]

    def __str__(self):
        return f"{self.get_suggestion_type_display()} — {self.title[:80]}"


# ── 11. Subscription-tier-gated feature tracking ───────────────────────────────

class TierFeatureUsage(models.Model):
    """Track daily usage against subscription tier limits."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="tier_feature_usages")
    feature = models.CharField(max_length=100)   # e.g. "ai_recommendations", "realtime_dashboard", "plan_comparison"
    tier = models.CharField(max_length=30)        # free / premium / enterprise
    day = models.DateField()
    count = models.IntegerField(default=0)
    limit = models.IntegerField(default=0)

    class Meta:
        db_table = "query_analytics_tier_feature_usage"
        unique_together = ["user", "feature", "day"]
        ordering = ["-day"]

    def __str__(self):
        return f"{self.user.email} — {self.feature} — {self.day} ({self.count}/{self.limit})"
