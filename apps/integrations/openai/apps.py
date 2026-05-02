"""Phase 12 — OpenAI integration Django app.

Registered in INSTALLED_APPS so AiPricing + AiUsageLog migrate.
The label is 'openai' so table names are 'openai_ai_pricing' / 'openai_ai_usage_log'.
ready() configures LangSmith env vars per CONTEXT.md best-effort decision.
"""

from __future__ import annotations

from django.apps import AppConfig


class OpenaiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations.openai"
    label = "openai"

    def ready(self) -> None:
        # Defer the import so collectstatic / makemigrations don't pull settings
        # before Django has finished bootstrapping. configure_langsmith reads
        # settings.LANGSMITH_ENABLED.
        from apps.integrations.openai.tracing import configure_langsmith

        configure_langsmith()
