from __future__ import annotations

from django.core.cache import cache

from apps.dashboard.filters import DashboardFilterParams

DASHBOARD_TTL_SECONDS = 300  # 5 minutes


def dashboard_cache_key(
    *, endpoint: str, org_id: int, user_id: int, params: DashboardFilterParams
) -> str:
    # django-redis applies KEY_PREFIX="app" automatically.
    return f"dashboard:{endpoint}:{org_id}:{user_id}:{params.filter_hash()}"


def cache_get(key: str) -> dict | None:  # type: ignore[type-arg]
    return cache.get(key)  # type: ignore[no-any-return]


def cache_set(key: str, data: dict, *, ttl: int = DASHBOARD_TTL_SECONDS) -> None:  # type: ignore[type-arg]
    cache.set(key, data, timeout=ttl)
