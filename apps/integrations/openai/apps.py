"""Phase 12 — OpenAI integration Django app.

Registered in INSTALLED_APPS so AiPricing + AiUsageLog migrate.
The label is 'openai' so table names are 'openai_ai_pricing' / 'openai_ai_usage_log'.
"""

from django.apps import AppConfig


class OpenaiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations.openai"
    label = "openai"
