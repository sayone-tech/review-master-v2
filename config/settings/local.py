from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "dev-insecure-secret"

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

DJANGO_VITE = {
    "default": {
        "dev_mode": True,
        "dev_server_host": "localhost",
        "dev_server_port": 5173,
        "manifest_path": BASE_DIR / "static" / "dist" / "manifest.json",  # noqa: F405
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "mailhog"
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
