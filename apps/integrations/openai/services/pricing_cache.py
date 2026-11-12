"""Cache invalidation for the AI pricing read caches (Phase 35).

The selectors in ``selectors/pricing.py`` populate these keys on read; every pricing change
(and the manual refresh endpoint) drops them here so reads stay side-effect free.
"""

from __future__ import annotations

from django.core.cache import cache

from apps.integrations.openai.selectors.pricing import MISSING_CACHE_KEY, RECENT_USAGE_CACHE_KEY


def invalidate_missing_pricing_cache() -> None:
    """Drop the missing-models result and the shared recent-usage aggregate."""
    cache.delete_many([MISSING_CACHE_KEY, RECENT_USAGE_CACHE_KEY])
