from .base import *

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
SECRET_KEY = env("DJANGO_SECRET_KEY")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Extra security headers — HRDG-02 (Phase 05)
SECURE_BROWSER_XSS_FILTER = True  # X-XSS-Protection: 1; mode=block
X_FRAME_OPTIONS = "DENY"  # Clickjacking protection (XFrameOptionsMiddleware reads this setting)

# Content Security Policy — Django 6 built-in (HRDG-02)
# Minimal permissive policy: 'unsafe-inline' on script/style is required for
# Alpine.js inline directives and Tailwind/Vite bundled CSS. Refine later once
# all inline handlers are migrated to external modules with nonces.
SECURE_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "connect-src": ["'self'"],
}

# Append CSP middleware to the base MIDDLEWARE list (Django 6 built-in).
# Placed near the bottom so any middleware that reads csp_nonce can run before it.
MIDDLEWARE = [*MIDDLEWARE, "django.middleware.csp.ContentSecurityPolicyMiddleware"]

# EMAIL_PROVIDER selects the outbound email backend.
# "resend" — Anymail + Resend API (default; no AWS approval needed)
# "ses"    — Amazon SES (switch once SES production access is granted)
_EMAIL_BACKEND_CHOICE = env("EMAIL_PROVIDER", default="resend")

if _EMAIL_BACKEND_CHOICE == "ses":
    EMAIL_BACKEND = "django_ses.SESBackend"
    AWS_SES_REGION_NAME = env("AWS_SES_REGION_NAME", default="us-east-1")
    AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
    AWS_SES_FROM_EMAIL = env("AWS_SES_FROM_EMAIL")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
    AWS_SES_CONFIGURATION_SET = env("AWS_SES_CONFIGURATION_SET", default=None)
elif _EMAIL_BACKEND_CHOICE == "resend":
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    INSTALLED_APPS = [*list(INSTALLED_APPS), "anymail"]
    ANYMAIL = {
        "RESEND_API_KEY": env("RESEND_API_KEY", default=""),
    }
else:
    raise ValueError(f"Unknown EMAIL_PROVIDER '{_EMAIL_BACKEND_CHOICE}'. Choose 'resend' or 'ses'.")

# Fernet salt key — single key (str) or list (rotation: [new, old])
SALT_KEY = env("FERNET_SALT_KEY")

# S3 static files — served from S3 in production (EC2 instance profile provides credentials)
INSTALLED_APPS = [*list(INSTALLED_APPS), "storages"]

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
AWS_LOCATION = "static"
AWS_DEFAULT_ACL = None  # inherit bucket policy (public-read set by Terraform)
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"

_S3_ORIGIN = f"https://{AWS_S3_CUSTOM_DOMAIN}"
SECURE_CSP["script-src"].append(_S3_ORIGIN)
SECURE_CSP["style-src"].append(_S3_ORIGIN)
SECURE_CSP["img-src"].append(_S3_ORIGIN)
SECURE_CSP["font-src"].append(_S3_ORIGIN)

# base.py does not define STORAGES — define both backends explicitly here.
# "default" keeps filesystem storage (no media uploads in scope).
# "staticfiles" routes collectstatic to S3.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    },
}
