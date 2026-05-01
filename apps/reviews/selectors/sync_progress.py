"""Phase 10 stub — Phase 11 will fetch progress state from Redis at sync:progress:{shop_id}."""

from typing import Any


async def get_progress_snapshot(*, shop_id: Any) -> dict[str, Any] | None:
    """Return the current progress snapshot for a shop, or None if no sync is in progress.

    Phase 10: always returns None (no syncs run yet).
    Phase 11: reads JSON from Redis key `sync:progress:{shop_id}` (24h/1h/7d TTLs per CLAUDE.md §7.7).
    """
    return None
