"""LiteLLM pricing auto-sync (Phase 36). Toggle only for now; the sync run lands in a later task."""

from __future__ import annotations

import logging

from django.db import transaction

from apps.accounts.models import User
from apps.common.models import AuditLog
from apps.integrations.openai.models import AiPricingSyncConfig

logger = logging.getLogger(__name__)


@transaction.atomic
def set_sync_enabled(*, enabled: bool, actor: User) -> AiPricingSyncConfig:
    """Flip the auto-sync switch; a no-op (no audit row) when the value is unchanged."""
    AiPricingSyncConfig.load()
    config = AiPricingSyncConfig.objects.select_for_update().get(pk=1)
    if config.enabled == enabled:
        return config
    before = config.enabled
    config.enabled = enabled
    config.save(update_fields=["enabled", "updated_at"])
    AuditLog.objects.create(
        organisation=None,
        actor=actor,
        entity_type="ai_pricing",
        entity_id="sync",
        action="ai_pricing.sync_enabled" if enabled else "ai_pricing.sync_disabled",
        before_data={"enabled": before},
        after_data={"enabled": enabled},
    )
    logger.info("ai_pricing.sync_toggled enabled=%s", enabled)
    return config
