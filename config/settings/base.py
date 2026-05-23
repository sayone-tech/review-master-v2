from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])

GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REDIRECT_URI = env(
    "GOOGLE_OAUTH_REDIRECT_URI", default="http://localhost:8000/oauth/google/callback/"
)

INSTALLED_APPS = [
    "daphne",  # MUST be first — overrides runserver for ASGI (RESEARCH.md Pitfall 2)
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "django_vite",
    "drf_spectacular",
    "django_celery_beat",
    # local
    "apps.common",
    "apps.accounts",
    "apps.organisations",
    "sequences",
    "apps.regions",
    "apps.shops",
    "apps.reviews",
    "apps.action_items",
    "apps.dashboard",
    "apps.notifications",
    "apps.reply_templates",
    "apps.integrations.openai",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://app:app@db:5432/reviewmaster")}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379") + "/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "app",
        "TIMEOUT": 300,
    },
    "throttle": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379") + "/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "throttle",
        "TIMEOUT": 900,
    },
}
DJANGO_REDIS_IGNORE_EXCEPTIONS = True
DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True

# ---------------------------------------------------------------------------
# Celery (introduced Phase 10) — broker DB 3, result backend DB 4
# See CLAUDE.md §12 for full architecture notes.
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379") + "/3"
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://redis:6379") + "/4"
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.reviews.tasks.sync_shop_reviews_task": {"queue": "google-sync"},
    "apps.reviews.tasks.initial_backfill_task": {"queue": "google-sync"},
    "apps.reviews.tasks.enrich_review_task": {"queue": "ai-enrichment"},
    "apps.reviews.tasks.retry_failed_enrichments_task": {"queue": "ai-enrichment"},
}
CELERY_TASK_TIME_LIMIT = 600  # 10-minute hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5-minute soft limit
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# ---------------------------------------------------------------------------
# Django Channels (introduced Phase 10) — channel layer DB 5
# See CLAUDE.md §13 for full architecture notes.
# WebSocket scope is intentionally narrow: only SyncProgressConsumer.
# ---------------------------------------------------------------------------
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://redis:6379") + "/5"],
            "capacity": 1500,
            "expiry": 30,
        },
    },
}

# ---------------------------------------------------------------------------
# OpenAI + LangSmith (introduced Phase 12) — single combined GPT-4o-mini call
# per review with structured-output parsing, time-versioned cost tracking,
# and best-effort LangSmith tracing.
# See CLAUDE.md §14 for full architecture notes.
# ---------------------------------------------------------------------------
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o-mini-2024-07-18")
OPENAI_MAX_RETRIES = env.int("OPENAI_MAX_RETRIES", default=3)
# Input cap for review text fed to OpenAI (D-21).
OPENAI_REVIEW_TEXT_MAX_CHARS = env.int("OPENAI_REVIEW_TEXT_MAX_CHARS", default=4000)

LANGSMITH_API_KEY = env("LANGSMITH_API_KEY", default=None)
LANGSMITH_ENDPOINT = env("LANGSMITH_ENDPOINT", default="https://api.smith.langchain.com")
LANGSMITH_PROJECT = env(
    "LANGSMITH_PROJECT",
    default=f"review-platform-{env('ENVIRONMENT', default='local')}",
)
LANGSMITH_ENABLED = bool(LANGSMITH_API_KEY)

INITIAL_SYNC_PAGE_SIZE = env.int("INITIAL_SYNC_PAGE_SIZE", default=50)
ENRICHMENT_BATCH_SIZE = env.int("ENRICHMENT_BATCH_SIZE", default=10)
INCREMENTAL_SYNC_INTERVAL_HOURS = env.int("INCREMENTAL_SYNC_INTERVAL_HOURS", default=6)
INCREMENTAL_SYNC_JITTER_MINUTES = env.int("INCREMENTAL_SYNC_JITTER_MINUTES", default=30)

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/admin/organisations/"
LOGOUT_REDIRECT_URL = "/login/"
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# Allow popup windows that navigate cross-origin (e.g. Google OAuth) to retain
# window.opener so postMessage can reach back to the main window.
# Django's SecurityMiddleware defaults to "same-origin" which severs window.opener
# when the popup navigates to a third-party domain (Google consent screen) and back.
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"

SESSION_COOKIE_AGE = (
    60 * 60 * 24
)  # 24 hours; CustomLoginView.form_valid overrides to 30 days when remember_me is checked
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

PASSWORD_RESET_TIMEOUT = 3600  # 1 hour (AUTH-04)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static", BASE_DIR / "logo"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django Unfold — admin theme
# ---------------------------------------------------------------------------
from django.templatetags.static import static  # noqa: E402


def _logo(request: object) -> str:
    return static("dashboard_logo.png")


def _icon(request: object) -> str:
    return static("mobile_logo.png")


UNFOLD = {
    "SITE_TITLE": "Review Master",
    "SITE_HEADER": "Review Master",
    "SITE_URL": "/admin/organisations/",
    "SITE_ICON": {"light": _icon, "dark": _icon},
    "SITE_LOGO": {"light": _logo, "dark": _logo},
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "32x32", "href": lambda r: static("favicon.ico")},
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "STYLES": [
        lambda r: static("admin/admin_custom.css"),
    ],
    "COLORS": {
        "base": {
            "50": "255 253 231",
            "100": "254 249 195",
            "200": "254 240 138",
            "300": "253 224 71",
            "400": "250 204 21",  # #FACC15 — brand yellow
            "500": "234 179 8",  # yellow-hover
            "600": "202 138 4",
            "700": "161 98 7",
            "800": "133 77 14",
            "900": "113 63 18",
            "950": "66 32 6",
        },
        "font": {
            "subtle-light": "107 114 128",
            "subtle-dark": "156 163 175",
            "default-light": "17 24 39",
            "default-dark": "243 244 246",
            "important-light": "0 0 0",
            "important-dark": "255 255 255",
        },
    },
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Admin",
                "items": [
                    {
                        "title": "Organisations",
                        "icon": "domain",
                        "link": "/django-admin/organisations/organisation/",
                    },
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "/django-admin/accounts/user/",
                    },
                    {
                        "title": "Shops",
                        "icon": "store",
                        "link": "/django-admin/shops/shop/",
                    },
                ],
            },
            {
                "title": "System",
                "items": [
                    {
                        "title": "Celery Beat",
                        "icon": "schedule",
                        "link": "/django-admin/django_celery_beat/periodictask/",
                    },
                    {
                        "title": "AI Pricing",
                        "icon": "payments",
                        "link": "/django-admin/openai/aipricing/",
                    },
                ],
            },
        ],
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/hour",
        "anon": "100/hour",
        "login": "10/15min",
        "review_reply": "30/minute",
        "generate_reply": "10/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    # 30-day refresh token with rotation+blacklist: stolen tokens can only be used once
    # before being invalidated. Tradeoff: longer window if attacker uses token first.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    # BLACKLIST_AFTER_ROTATION requires token_blacklist migrations to be applied before
    # the refresh endpoint is called, or it will raise an OperationalError at runtime.
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    # HS256 + SECRET_KEY: rotating SECRET_KEY invalidates all outstanding tokens.
    # Migrate to RS256 if zero-downtime key rotation is ever needed.
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Review Master API",
    "DESCRIPTION": "Internal API for web and mobile clients. Not for external use.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"jwtAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "jwtAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

DJANGO_VITE = {
    "default": {
        "dev_mode": env.bool("DJANGO_VITE_DEV_MODE", default=False),
        "dev_server_host": env("DJANGO_VITE_DEV_SERVER_HOST", default="localhost"),
        "dev_server_port": 5173,
        "static_url_prefix": "dist",
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",
    }
}

# SES / email — production.py overrides this to SES; local.py → MailHog SMTP
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
DEFAULT_REPLY_TO = env("DEFAULT_REPLY_TO", default="support@example.com")

# Field-level encryption — django-fernet-encrypted-fields uses SALT_KEY
# (NOT FERNET_KEYS — wrong name silently falls back to Django SECRET_KEY).
ENCRYPTED_FIELD_MODE = "ENCRYPT_AND_DECRYPT"
SALT_KEY = env("FERNET_SALT_KEY", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ---------------------------------------------------------------------------
# Sentry (introduced Phase 10) — error capture for web AND Celery worker
# See CLAUDE.md §21 and CONTEXT.md "Sentry integration" decision.
# Active ONLY when SENTRY_DSN is set. Local dev and tests have no DSN -> silent.
# ---------------------------------------------------------------------------
import sentry_sdk  # noqa: E402
from sentry_sdk.integrations.celery import CeleryIntegration  # noqa: E402
from sentry_sdk.integrations.django import DjangoIntegration  # noqa: E402
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber  # noqa: E402
from sentry_sdk.types import Event  # noqa: E402

_SENSITIVE_SUBSTRINGS = frozenset(
    {"email", "token", "key", "secret", "password", "refresh", "access"}
)


def _before_send(event: Event, hint: dict[str, object]) -> Event | None:
    """Recursively scrub fields whose key contains any sensitive substring.

    See CONTEXT.md locked decision and CLAUDE.md §22.
    """

    def _scrub(obj: object) -> object:
        if isinstance(obj, dict):
            return {
                k: (
                    "[Filtered]"
                    if any(s in str(k).lower() for s in _SENSITIVE_SUBSTRINGS)
                    else _scrub(v)
                )
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_scrub(item) for item in obj]
        return obj

    return _scrub(event)  # type: ignore[return-value]


SENTRY_DSN = env("SENTRY_DSN", default=None)
ENVIRONMENT = env("ENVIRONMENT", default="local")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(propagate_traces=True),
        ],
        send_default_pii=False,
        event_scrubber=EventScrubber(
            denylist=[*DEFAULT_DENYLIST, "organisation_id"],
            recursive=True,
        ),
        before_send=_before_send,
        traces_sample_rate=0.1,
    )
