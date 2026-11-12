"""Deploy-time system check: the configured OpenAI model must have an active price.

Runs only for ``manage.py check --deploy --database <alias>``: ``deploy=True`` keeps it
out of ``migrate`` / ``runserver`` / plain ``check``, and the database tag means
``check --deploy`` without ``--database`` (CI) never touches the database.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Tags, register
from django.core.checks import Warning as CheckWarning
from django.db.utils import OperationalError, ProgrammingError

from apps.integrations.openai.models import AiPricing


@register(Tags.database, deploy=True)
def check_configured_model_priced(
    app_configs: Any, databases: Any = None, **kwargs: Any
) -> list[CheckMessage]:
    if not databases:
        return []
    model = settings.OPENAI_MODEL
    try:
        AiPricing.objects.get_active(model=model)
    except AiPricing.DoesNotExist:
        return [
            Error(
                f"OPENAI_MODEL '{model}' has no active AiPricing row.",
                hint="Add a price on /admin/ai-pricing/ before deploying.",
                id="openai.E001",
            )
        ]
    except (ProgrammingError, OperationalError):
        return [
            CheckWarning(
                "Could not read AiPricing (table missing? migrations pending).",
                id="openai.W001",
            )
        ]
    return []
