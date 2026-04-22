from .base import *

DEBUG = False
SECRET_KEY = "test-insecure-secret"  # nosec B105  # noqa: S105

# Only include apps that exist at this stage; later plans add accounts/organisations
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "drf_spectacular",
    # local
    "apps.common",
]

# Use the built-in User until Plan 02 creates the custom user model
AUTH_USER_MODEL = "auth.User"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


# Disable migrations for speed
class DisableMigrations:
    def __contains__(self, item: object) -> bool:
        return True

    def __getitem__(self, item: object) -> None:
        return None


MIGRATION_MODULES = DisableMigrations()

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
