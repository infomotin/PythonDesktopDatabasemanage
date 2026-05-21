import os
import sys
from pathlib import Path

import environ
env = environ.Env(
    DEBUG=(bool, False),
    SECURE_SSL_REDIRECT=(bool, False),
    SESSION_COOKIE_SECURE=(bool, False),
    CSRF_COOKIE_SECURE=(bool, False),
)
BASE_DIR = Path(__file__).resolve().parent.parent
env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-kilo-dbms-2024-secure-key-change-in-production")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "crispy_forms",
    "crispy_tailwind",
    "storages",
    "channels",
    "apps.core",
    "apps.users",
    "apps.connections",
    "apps.databases",
    "apps.tables",
    "apps.query_builder",
    "apps.import_export",
    "apps.seeding",
    "apps.analytics",
    "apps.subscription",
    "apps.notifications",
    "apps.workspaces",
    "apps.query_analytics",
    "apps.db_query_history",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestLoggingMiddleware",
    "apps.core.middleware.ExceptionLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.dbms_settings",
                "apps.core.context_processors.user_connections",
                "apps.subscription.context_processors.user_subscription",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "dashboard:index"
LOGOUT_REDIRECT_URL = "users:login"

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="kilo-dbms-encryption-key-2024")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@dbmspro.com")

STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_SUCCESS_URL = env("STRIPE_SUCCESS_URL", default="/subscription/success/")
STRIPE_CANCEL_URL = env("STRIPE_CANCEL_URL", default="/subscription/cancel/")

os.makedirs(BASE_DIR / "logs", exist_ok=True)
os.makedirs(BASE_DIR / "exports", exist_ok=True)
os.makedirs(BASE_DIR / "temp", exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {message}", "style": "{"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "dbms.log",
            "formatter": "verbose",
        },
        "console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["file"], "level": "INFO"},
    "loggers": {"django": {"handlers": ["file", "console"], "level": "INFO", "propagate": False}},
}

# ─── Query Analytics & Performance Monitoring ─────────────────
QA_SLOW_QUERY_THRESHOLD_MS         = int(os.environ.get("SLOW_QUERY_THRESHOLD_MS", "500"))
QA_ALERT_CPU_THRESHOLD_PCT         = float(os.environ.get("ALERT_CPU_THRESHOLD_PCT", "85"))
QA_ALERT_MEM_THRESHOLD_MB          = float(os.environ.get("ALERT_MEM_THRESHOLD_MB", "512"))
QA_ALERT_DURATION_CRITICAL_MS      = float(os.environ.get("ALERT_DURATION_CRITICAL_MS", "3000"))
QA_ALERT_DURATION_WARNING_MS       = float(os.environ.get("ALERT_DURATION_WARNING_MS", "500"))
QA_ALERT_POOL_SATURATION_PCT       = float(os.environ.get("ALERT_POOL_SATURATION_PCT", "90"))
QA_ALERT_RATE_LIMIT_SECONDs        = float(os.environ.get("ALERT_RATE_LIMIT_SECONDS", "60"))
QA_RECOMMENDATION_MIN_OCCURRENCES  = int(os.environ.get("RECOMMENDATION_MIN_OCCURRENCES", "3"))
QA_RECOMMENDATION_MAX_PER_RUN      = int(os.environ.get("RECOMMENDATION_MAX_PER_RUN", "20"))
QA_METRIC_RETENTION_DAYS           = int(os.environ.get("QA_METRIC_RETENTION_DAYS", "365"))
QA_REALTIME_WINDOW_SECONDS         = int(os.environ.get("QA_REALTIME_WINDOW_SECONDS", "300"))
QA_OPTIMIZATION_MIN_SCORE_PCT      = float(os.environ.get("OPTIMIZATION_MIN_SCORE_PCT", "10"))
QA_TRIGGER_ENGINES                 = os.environ.get("QA_TRIGGER_ENGINES",
                                                  "slow_query,alert,optimization,recommendation").split(",")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["https://localhost", "https://127.0.0.1"])
