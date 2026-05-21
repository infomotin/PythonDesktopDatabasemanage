import uuid

from django.db import models


class DataRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="data_runs")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_ping = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="created_data_runs"
    )
    credentials = models.JSONField(default=dict)
    scheduled_run = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    workspace = models.ForeignKey("workspaces.Workspace", on_delete=models.SET_NULL, null=True, blank=True)
    owner = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="owned_data_runs"
    )
    cron_expression = models.CharField(max_length=100, blank=True)
    recurrence = models.CharField(max_length=20, default="once")
    node_executions = models.JSONField(default=list, blank=True)
    run_data = models.JSONField(default=dict, blank=True)
    saved_queries = models.JSONField(default=list, blank=True)
    data_sources = models.JSONField(default=list, blank=True)
    is_connected = models.BooleanField(default=False)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    python_version = models.CharField(max_length=20, blank=True)
    path = models.CharField(max_length=512, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    run_count = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    run_count = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    run_count = models.JSONField(default=list, blank=True)
    success_rate = models.FloatField(default=0)
    avg_duration = models.FloatField(default=0)
    token_price_map = models.JSONField(default=dict)
    run_count = models.JSONField(default=list, blank=True)
    git_repo_url = models.URLField(blank=True)
    git_commit_hash = models.CharField(max_length=40, blank=True)
    cpu_limit = models.IntegerField(null=True, blank=True)
    memory_limit = models.CharField(max_length=20, blank=True)
    system_prompt = models.TextField(blank=True, default="You are a data analyst AI agent.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    def add_node_execution(self, node_id, node_name, status, data, duration_sec=0):
        self.node_executions = self.node_executions or []
        self.node_executions.append({
            "id": node_id,
            "name": node_name,
            "status": status,
            "data": data,
            "duration_sec": duration_sec,
            "timestamp": timezone.now().isoformat(),
        })
        self.save(update_fields=["node_executions"])

    def mark_completed(self):
        from django.utils import timezone
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_plan_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    create_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} (${self.price}/mo)"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="documents/")
    file_size = models.BigIntegerField(default=0)
    total_pages = models.IntegerField(default=0)
    total_words = models.BigIntegerField(default=0)
    total_tables = models.IntegerField(default=0)
    total_charts = models.IntegerField(default=0)
    total_images = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    content = models.TextField(blank=True, default="")
    is_shared = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Hook(models.Model):
    METHOD_CHOICES = [("GET", "GET"), ("POST", "POST"), ("PUT", "PUT"), ("DELETE", "DELETE"), ("PATCH", "PATCH")]
    AUTH_TYPE_CHOICES = [("none", "None"), ("basic", "Basic Auth"), ("bearer", "Bearer Token"), ("api_key", "API Key")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey("accounts.SubAccount", on_delete=models.CASCADE, related_name="hooks")
    name = models.CharField(max_length=255)
    target_url = models.URLField()
    http_method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="POST")
    headers = models.JSONField(default=dict, blank=True)
    body = models.TextField(blank=True, default="{}")
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES, default="none")
    auth_credentials = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    retry_count = models.IntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, blank=True)
    created_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="created_hooks")
    webhook_secret = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.account.name})"

    def get_decrypted_credentials(self):
        if not self.auth_credentials:
            return {}
        from apps.core.crypto import decrypt_credential
        try:
            return json.loads(decrypt_credential(self.auth_credentials))
        except Exception:
            return {"raw": self.auth_credentials}


class EmailTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    body_html = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SMTPProvider(models.Model):
    EMAIL_BACKEND_CHOICES = [("smtp", "SMTP"), ("ses", "Amazon SES"), ("sendgrid", "SendGrid"), ("mailgun", "Mailgun"), ("postmark", "Postmark")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    email_backend = models.CharField(max_length=20, choices=EMAIL_BACKEND_CHOICES, default="smtp")
    from_email = models.EmailField()
    host = models.CharField(max_length=255, blank=True)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255, blank=True)
    password = models.TextField(blank=True)
    api_key = models.TextField(blank=True)
    api_secret = models.TextField(blank=True)
    api_region = models.CharField(max_length=50, blank=True)
    use_ssl = models.BooleanField(default=False)
    use_tls = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    test_status = models.CharField(max_length=20, blank=True)
    last_test_error = models.TextField(blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_email_backend_display()})"


class DefaultSender(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    default_from_name = models.CharField(max_length=255)
    default_from_email = models.EmailField()
    smtp_provider = models.ForeignKey(SMTPProvider, on_delete=models.SET_NULL, null=True, blank=True)
    reply_to_name = models.CharField(max_length=255, blank=True)
    reply_to_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmailLog(models.Model):
    STATUSES = [("sent", "Sent"), ("delivered", "Delivered"), ("opened", "Opened"),
                ("clicked", "Clicked"), ("bounced", "Bounced"), ("dropped", "Dropped"), ("failed", "Failed")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey("accounts.SubAccount", on_delete=models.CASCADE, related_name="email_logs")
    provider = models.ForeignKey(SMTPProvider, on_delete=models.CASCADE, related_name="email_logs")
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=255, blank=True)
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=512)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUSES, default="sent")
    opens = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    bounces = models.IntegerField(default=0)
    complaints = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    delivery_status = models.CharField(max_length=50, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.subject} → {self.recipient_email}"


class BrowserAutomation(models.Model):
    STATUS_CHOICES = [("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="browser_automations")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    browser = models.CharField(max_length=20, default="chrome")
    script = models.TextField(blank=True, help_text=_("Python script or DSL"))
    schedule = models.CharField(max_length=100, blank=True, help_text=_("Cron expression"))
    devices = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    last_run = models.DateTimeField(null=True, blank=True)
    last_result = models.JSONField(default=dict, blank=True)
    total_runs = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    created_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="browser_automations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    @property
    def success_rate(self):
        if self.total_runs == 0:
            return 0.0
        return (self.success_count / self.total_runs) * 100

    def mark_run(self, success: bool):
        self.total_runs += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_run = timezone.now()
        self.save(update_fields=["total_runs", "success_count", "failure_count", "last_run"])


class Credential(models.Model):
    TYPE_CHOICES = [("api_key", "API Key"), ("username_password", "Username / Password"), ("ssh_private_key", "SSH Private Key"),
                    ("database_password", "Database Password"), ("oauth_token", "OAuth Token")]
    ENCRYPTION_CHOICES = [("aes_256_gcm", "AES-256-GCM"), ("xchacha20_poly1305", "Xchacha20-Poly1305")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey("accounts.SubAccount", on_delete=models.CASCADE, related_name="credentials")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="credentials")
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="api_key")
    username = models.CharField(max_length=255, blank=True)
    password = models.CharField(max_length=255, blank=True)
    key = models.CharField(max_length=512, blank=True, help_text=_("API key / OAuth token"))
    note = models.TextField(blank=True)
    encryption = models.CharField(max_length=50, choices=ENCRYPTION_CHOICES, default="aes_256_gcm")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"





class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    billing_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MCPTool(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    schema = models.JSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="mcp_tools")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Provider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=50, default="api")
    credentials_enc = models.TextField(blank=True)
    endpoint_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="providers")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="own_workspaces")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.SET_NULL, null=True, blank=True)
    team = models.JSONField(default=list, blank=True)
    members = models.ManyToManyField("users.User", related_name="workspaces", blank=True)
    is_public = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    bot_name = models.CharField(max_length=255, blank=True)  # New field for bot name
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name