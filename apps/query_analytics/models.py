import re as _re
import uuid
import hashlib

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# ---------------------------------------------------------------------------
# Enums / Choices shared across models
# ---------------------------------------------------------------------------
class ConnectionState(models.TextChoices):
    IDLE = "idle", _("Idle")
    ACTIVE = "active", _("Active")
    BUSY = "busy", _("Busy")
    SATURATED = "saturated", _("Saturated")


class SqlEngine(models.TextChoices):
    MYSQL = "mysql", _("MySQL")
    POSTGRESQL = "postgresql", _("PostgreSQL")
    ORACLE = "oracle", _("Oracle")
    MONGODB = "mongodb", _("MongoDB")
    SQLITE = "sqlite", _("SQLite")
    SQLSERVER = "sqlserver", _("SQL Server")
    MARIADB = "mariadb", _("MariaDB")
    COCKROACHDB = "cockroachdb", _("CockroachDB")


class MetricStatus(models.TextChoices):
    SUCCESS = "success", _("Success")
    WARNING = "warning", _("Warning")
    CRITICAL = "critical", _("Critical")
    ERROR = "error", _("Error")


class AlertPriority(models.TextChoices):
    LOW = "low", _("Low")
    MEDIUM = "medium", _("Medium")
    HIGH = "high", _("High")
    CRITICAL = "critical", _("Critical")


class IndexType(models.TextChoices):
    BTREE = "b_tree", _("B-Tree")
    HASH = "hash", _("Hash")
    GIST = "gist", _("GiST")
    GIN = "gin", _("GIN")
    BITMAP = "bitmap", _("Bitmap")
    INNODB = "innodb", _("InnoDB")
    MYISAM = "myisam", _("MyISAM")
    HASH_MYSQL = "hash_mysql", _("Hash (MySQL)")


class RecommendationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    APPLIED = "applied", _("Applied")
    DISMISSED = "dismissed", _("Dismissed")
    EXPIRED = "expired", _("Expired")


class SlowQueryStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    INVESTIGATING = "investigating", _("Investigating")
    RESOLVED = "resolved", _("Resolved")
    IGNORED = "ignored", _("Ignored")


class Order(models.TextChoices):
    ASC = "asc", "ASC"
    DESC = "desc", "DESC"


class TemplateType(models.TextChoices):
    COUNT = "count", _("Count")
    TIMESERIES = "timeseries", _("Time Series")
    HEATMAP = "heatmap", _("Heatmap")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _query_hash(sql: str) -> str:
    """Deterministic hash for a normalised SQL / query string."""
    normalized = re.sub(r"\s+", "", sql).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 1.  DatabaseConnection (FK shortcut model – points to connections app)
# ---------------------------------------------------------------------------
class ConnectionSnapshot(models.Model):
    """
    Periodic snapshot of a user's external database connection pool state.

    Records: active/idle/total connections, max pool capacity, and a
    state label derived from usage thresholds.
    """
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.CASCADE,
        related_name="analytics_pool_metrics",
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    active_connections = models.IntegerField(default=0)
    idle_connections = models.IntegerField(default=0)
    total_connections = models.IntegerField(default=0)
    max_capacity = models.IntegerField(default=100)
    state = models.CharField(
        max_length=20, choices=ConnectionState.choices, default=ConnectionState.IDLE
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["connection", "-timestamp"])]

    def usage_pct(self) -> float:
        cap = self.max_capacity or 1
        return round(self.total_connections / cap * 100, 1)

    def __str__(self):
        return f"{self.connection} — {self.timestamp:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# 2.  QueryExecutionPlan
# ---------------------------------------------------------------------------
class QueryExecutionPlan(models.Model):
    """
    Stores the raw execution plan string and a parsed JSON breakdown
    returned by EXPLAIN/ANALYZE (SQL) or the aggregation pipeline
    introspection API (MongoDB).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engine = models.CharField(max_length=30, choices=SqlEngine.choices)
    plan_text = models.TextField(help_text=_("Raw EXPLAIN / aggregation output"))
    parsed_plan = models.JSONField(
        default=dict, blank=True,
        help_text=_("Structured JSON representation of the plan steps"),
    )
    total_cost = models.FloatField(default=0, help_text=_("Estimated or actual plan cost"))
    execution_time_ms = models.FloatField(
        default=0, help_text=_("ANALYZE-reported actual execution time in ms")
    )
    rows_examined = models.BigIntegerField(default=0)
    rows_returned = models.BigIntegerField(default=0)
    indexes_used = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.engine} plan — {self.created_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# 3.  QueryMetric  (primary per-query time-series record)
# ---------------------------------------------------------------------------
class QueryMetric(models.Model):
    """
    One row per query execution.  Holds all raw timing / resource numbers
    collected by the middleware / collector.

    A short-lived in-memory dictionary middleware writes a row here for
    every query that passes through the DBMS.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- FKs ---
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="query_metrics",
    )
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name="analytics_metrics",
    )
    # FK to the optional QueryHistory entry created by the query executor
    query_history = models.ForeignKey(
        "db_query_history.QueryHistory",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name="analytics_metrics",
    )
    # FK to the execution plan (populated for slow queries)
    execution_plan = models.ForeignKey(
        QueryExecutionPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name="metrics",
    )

    # --- Identity ---
    normalized_hash = models.CharField(
        max_length=64, db_index=True,
        help_text=_("SHA-256 hash of the normalised query text (dedup/grouping)"),
    )
    engine = models.CharField(max_length=30, choices=SqlEngine.choices, db_index=True)
    query_type = models.CharField(max_length=20, default="other")

    # The full query text – truncated in storage for security / performance.
    # Full-length text is only kept if `QUERY_METRICS_FULL_TEXT_DAYS` env is set.
    query_text = models.TextField(
        help_text=_("Truncated query text; full text purged by cleanup policy")
    )
    query_label = models.CharField(
        max_length=255, blank=True,
        help_text=_("Auto-labelled from query builder SavedQuery name"),
    )

    # --- Metrics ---
    duration_ms = models.FloatField(default=0, db_index=True)
    rows_affected = models.BigIntegerField(default=0)
    memory_consumed_mb = models.FloatField(default=0)
    cpu_percent = models.FloatField(default=0)

    # --- Status ---
    status = models.CharField(
        max_length=20, choices=MetricStatus.choices, default=MetricStatus.SUCCESS,
    )
    error_message = models.TextField(blank=True, default="")

    # --- Temporal ---
    executed_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Subscription guard ---
    is_slow = models.BooleanField(default=False, db_index=True)

    # --- Tags ---
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["user", "-executed_at"]),
            models.Index(fields=["engine", "-executed_at"]),
            models.Index(fields=["is_slow", "-executed_at"]),
            models.Index(fields=["normalized_hash", "user"]),
            models.Index(fields=["connection", "-executed_at"]),
        ]

    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.normalized_hash:
            raw = self.query_text
            if self.query_history_id and self.query_history:
                raw = self.query_history.query
            self.normalized_hash = _query_hash(raw)
        if not self.query_label and self.query_history_id:
            try:
                qh = type(self).objects.select_related("query_history").get(
                    pk=self.pk
                ).query_history
                self.query_label = qh.query[:80] if qh else ""
            except Exception:
                pass
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    def is_warning(self):
        return self.status == MetricStatus.WARNING

    def is_critical(self):
        return self.status == MetricStatus.CRITICAL

    def is_error(self):
        return self.status == MetricStatus.ERROR

    def __str__(self):
        label = self.query_label or self.query_text[:60]
        return f"[{self.engine}] {label} — {self.duration_ms:.1f}ms"


# ---------------------------------------------------------------------------
# 4.  MetricAggregate  (pre-aggregated roll-up)
# ---------------------------------------------------------------------------
class MetricAggregate(models.Model):
    """
    Pre-aggregated metrics bucketed by time window.  Produced by the
    nightly / hourly aggregate worker so dashboards don’t scan millions
    of QueryMetric rows at runtime.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="metric_aggregates",
    )
    engine = models.CharField(max_length=30, choices=SqlEngine.choices)
    granularity = models.CharField(
        max_length=10,
        choices=[("1m", "1 min"), ("5m", "5 min"), ("15m", "15 min"),
                 ("1h", "1 hour"), ("1d", "1 day")],
        default="5m",
    )
    bucket_start = models.DateTimeField(db_index=True)

    avg_duration_ms = models.FloatField(default=0)
    max_duration_ms = models.FloatField(default=0)
    min_duration_ms = models.FloatField(default=0)
    p95_duration_ms = models.FloatField(default=0)
    p99_duration_ms = models.FloatField(default=0)
    query_count = models.IntegerField(default=0)
    total_rows = models.BigIntegerField(default=0)
    avg_memory_mb = models.FloatField(default=0)
    avg_cpu_pct = models.FloatField(default=0)
    error_count = models.IntegerField(default=0)
    slow_query_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ["user", "engine", "granularity", "bucket_start"]
        ordering = ["-bucket_start"]
        indexes = [models.Index(fields=["user", "engine", "-bucket_start"])]

    def __str__(self):
        return f"{self.engine} — {self.granularity} — {self.bucket_start:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# 5.  SlowQuery  (persistent slow-query tracker)
# ---------------------------------------------------------------------------
class SlowQuery(models.Model):
    """
    A query that crossed the configurable SLOW_QUERY_THRESHOLD_MS.
    Tracks state transitions so engineers can mark issues as resolved
    without losing the historical record.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="slow_queries",
    )
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="slow_queries",
    )
    normalized_hash = models.CharField(max_length=64, db_index=True)
    query_text = models.TextField()
    query_type = models.CharField(max_length=20, default="other")
    engine = models.CharField(max_length=30, choices=SqlEngine.choices)

    avg_duration_ms = models.FloatField(default=0)
    max_duration_ms = models.FloatField(default=0)
    occurrence_count = models.IntegerField(default=1)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    first_seen = models.DateTimeField(default=timezone.now)

    status = models.CharField(
        max_length=20, choices=SlowQueryStatus.choices,
        default=SlowQueryStatus.ACTIVE,
    )
    threshold_ms = models.FloatField(
        default=500,
        help_text=_("Threshold in effect when this was flagged"),
    )

    class Meta:
        ordering = ["-last_seen"]
        indexes = [
            models.Index(fields=["user", "status", "-last_seen"]),
            models.Index(fields=["normalized_hash"]),
        ]

    def increment(self, duration_ms: float):
        self.occurrence_count = models.F("occurrence_count") + 1
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.last_seen = timezone.now()
        self.save(update_fields=["occurrence_count", "max_duration_ms", "last_seen"])

    def __str__(self):
        return f"Slow[{self.status}] {self.query_text[:60]} — avg {self.avg_duration_ms:.0f}ms"


# ---------------------------------------------------------------------------
# 6.  IndexRecommendation
# ---------------------------------------------------------------------------
class IndexRecommendation(models.Model):
    """
    Engine-specific index suggestion generated by the recommendation engine.
    Each recommendation is scored and linked to the slow queries that
    motivated it.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="index_recommendations",
    )
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.CASCADE, related_name="index_recommendations",
    )
    slow_queries = models.ManyToManyField(
        SlowQuery, blank=True, related_name="recommendations",
    )

    engine = models.CharField(max_length=30, choices=SqlEngine.choices)
    table_name = models.CharField(max_length=255)
    schema_name = models.CharField(max_length=255, blank=True, default="")
    column_names = models.JSONField(default=list, blank=True, help_text=_("List of columns to index"))

    index_type = models.CharField(
        max_length=30, choices=IndexType.choices, default=IndexType.BTREE,
    )
    index_name_suggestion = models.CharField(max_length=255, blank=True)
    create_statement = models.TextField(
        help_text=_("Ready-to-run CREATE INDEX statement"),
    )

    score = models.FloatField(
        default=0,
        help_text=_("0–100 estimated performance improvement score"),
    )
    estimated_improvement_pct = models.FloatField(
        default=0,
        help_text=_("Estimated execution-time reduction as a percentage"),
    )
    rationale = models.TextField(
        blank=True,
        help_text=_("Natural-language explanation of why the index helps"),
    )

    status = models.CharField(
        max_length=20, choices=RecommendationStatus.choices,
        default=RecommendationStatus.PENDING,
    )
    priority = models.CharField(
        max_length=10, choices=AlertPriority.choices,
        default=AlertPriority.MEDIUM,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    dismissed_reason = models.CharField(max_length=255, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-score", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["engine", "table_name"]),
        ]

    def is_pending(self):
        return self.status == RecommendationStatus.PENDING

    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at

    def __str__(self):
        return f"IdxRec [{self.score}] {self.table_name}({','.join(self.column_names)})"


# ---------------------------------------------------------------------------
# 7.  QueryOptimizationSuggestion  (AI-powered)
# ---------------------------------------------------------------------------
class QueryOptimizationSuggestion(models.Model):
    """
    Each row is one optimisation tip generated for a specific QueryMetric
    (or SlowQuery).  The tip includes a rewritten query variant and an
    estimated performance gain.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="optimization_suggestions",
    )
    query_metric = models.ForeignKey(
        QueryMetric,
        on_delete=models.CASCADE,
        related_name="optimization_suggestions",
        null=True, blank=True,
    )
    slow_query = models.ForeignKey(
        SlowQuery,
        on_delete=models.CASCADE,
        related_name="optimization_suggestions",
        null=True, blank=True,
    )
    execution_plan = models.ForeignKey(
        QueryExecutionPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="optimization_suggestions",
    )

    engine = models.CharField(max_length=30, choices=SqlEngine.choices)
    suggestion_type = models.CharField(
        max_length=50, blank=True,
        help_text=_(
            "e.g. missing_index, unnecessary_join, subquery_extraction, "
            "join_reorder, aggregation_pushdown, limit_early"
        ),
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    rationale = models.TextField(
        blank=True,
        help_text=_("Why this change improves performance"),
    )
    estimated_improvement_pct = models.FloatField(
        default=0,
        help_text=_("Estimated speed-up percentage"),
    )

    # The rewritten SQL / pipeline text
    original_query = models.TextField(blank=True)
    optimized_query = models.TextField(blank=True)

    confidence = models.CharField(
        max_length=10,
        choices=[("low", _("Low")), ("medium", _("Medium")), ("high", _("High"))],
        default="medium",
    )

    # The engine used when this was generated  (same as engine in most cases)
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-estimated_improvement_pct", "-created_at"]
        indexes = [models.Index(fields=["user", "engine"])]

    def __str__(self):
        return f"Opt [{self.engine}] {self.title} — +{self.estimated_improvement_pct}%"


# ---------------------------------------------------------------------------
# 8.  QueryComparison
# ---------------------------------------------------------------------------
class QueryComparison(models.Model):
    """
    Stores a comparison session: one or more QueryMetric results side-by-side
    (same query, same dataset, different engines or different parameter sets).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="query_comparisons",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")

    metrics = models.ManyToManyField(
        QueryMetric, blank=True, related_name="comparisons",
    )

    winner_engine = models.CharField(
        max_length=30, choices=SqlEngine.choices, blank=True
    )
    winner_reason = models.CharField(max_length=255, blank=True, default="")

    fastest_duration_ms = models.FloatField(default=0)
    slowest_duration_ms = models.FloatField(default=0)
    avg_duration_ms = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Query Comparison")
        verbose_name_plural = _("Query Comparisons")

    def __str__(self):
        return f"Comparison {self.pk.hex[:8]} — {self.name or 'unnamed'}"


# ---------------------------------------------------------------------------
# 9.  PerformanceAlert
# ---------------------------------------------------------------------------
class PerformanceAlert(models.Model):
    """
    Triggered when a resource bound is exceeded.  Surfaced in the
    dashboard UI and optionally sent as an in-app notification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="performance_alerts",
        null=True, blank=True,
    )
    # null user = system-wide / administrator alert
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.CASCADE, null=True, blank=True,
        related_name="performance_alerts",
    )

    alert_type = models.CharField(
        max_length=50, blank=True,
        help_text=_("e.g. cpu_spike, memory_pressure, pool_saturation, long_transaction"),
    )
    priority = models.CharField(
        max_length=10, choices=AlertPriority.choices, default=AlertPriority.MEDIUM,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    metric_snapshot = models.JSONField(
        default=dict, blank=True,
        help_text=_("Snapshot of metrics at alert time"),
    )

    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def acknowledge(self):
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["acknowledged", "acknowledged_at"])

    def resolve(self):
        self.resolved = True
        self.resolved_at = timezone.now()
        self.save(update_fields=["resolved", "resolved_at"])

    def __str__(self):
        return f"[{self.priority}] {self.title} — {self.created_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# 10.  QueryLabel  (named query registry for cross-run tracking)
# ---------------------------------------------------------------------------
class QueryLabel(models.Model):
    """
    Optional manual or auto-generated label that groups multiple query
    executions of the same logical query.  Enables per-label historical
    trend tracking in the dashboard.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="query_labels",
    )
    connection = models.ForeignKey(
        "connections.DatabaseConnection",
        on_delete=models.CASCADE, null=True, blank=True,
        related_name="query_labels",
    )
    normalized_hash = models.CharField(max_length=64, db_index=True)
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    engine = models.CharField(max_length=30, choices=SqlEngine.choices)
    is_favorite = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "normalized_hash"]
        ordering = ["-is_favorite", "-updated_at"]

    def __str__(self):
        return self.label
