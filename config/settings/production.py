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
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'"],
}

# Append CSP middleware to the base MIDDLEWARE list (Django 6 built-in).
# Placed near the bottom so any middleware that reads csp_nonce can run before it.
MIDDLEWARE = [*MIDDLEWARE, "django.middleware.csp.ContentSecurityPolicyMiddleware"]

EMAIL_BACKEND = "django_ses.SESBackend"
AWS_SES_REGION_NAME = env("AWS_SES_REGION_NAME", default="us-east-1")
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
AWS_SES_FROM_EMAIL = env("AWS_SES_FROM_EMAIL")
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
AWS_SES_CONFIGURATION_SET = env("AWS_SES_CONFIGURATION_SET", default=None)
