from .base import *

DEBUG = False
SECRET_KEY = "test-insecure-secret"  # nosec B105  # noqa: S105

# Plan 02: accounts and organisations apps are now available
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
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
]

AUTH_USER_MODEL = "accounts.User"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "throttle": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SALT_KEY = "test-salt-key-for-unit-tests-only-32chars"

DJANGO_VITE = {
    "default": {
        "dev_mode": True,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "static_url_prefix": "dist",
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",
    }
}

# Celery — eager mode for tests (no broker needed)
# See CLAUDE.md §12.8 and §16
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
