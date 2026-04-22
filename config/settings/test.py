from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-insecure-secret"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


# Disable migrations for speed
class DisableMigrations:
    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        return True

    def __getitem__(self, item: object) -> None:
        return None


MIGRATION_MODULES = DisableMigrations()

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
