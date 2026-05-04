"""Phase 12 — LangSmith configuration.

Called from OpenaiConfig.ready() so LangSmith env vars are set BEFORE any
langsmith module is imported (RESEARCH.md Pitfall 4). When LangSmith is
disabled (no API key, or test settings), LANGSMITH_TRACING=false makes
@traceable a pass-through — no network attempt, no exception.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Set LangSmith env vars based on Django settings.

    Idempotent — safe to call multiple times. Always assigns LANGSMITH_TRACING
    so re-imports don't pick up stale state from a previous configuration.
    """
    enabled = getattr(settings, "LANGSMITH_ENABLED", False)
    if enabled:
        api_key = getattr(settings, "LANGSMITH_API_KEY", "") or ""
        project = getattr(settings, "LANGSMITH_PROJECT", "review-platform")
        endpoint = getattr(settings, "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGSMITH_ENDPOINT"] = endpoint
        logger.info("langsmith_configured project=%s endpoint=%s", project, endpoint)
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.debug("langsmith_disabled")
