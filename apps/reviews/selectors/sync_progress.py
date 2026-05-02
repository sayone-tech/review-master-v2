"""Phase 11 — async wrapper around the sync.progress Redis reader.

The consumer awaits this on connect (PROG-09) so the reconnecting client
sees the current snapshot without waiting for the next event.
"""

from __future__ import annotations

from typing import Any

from channels.db import database_sync_to_async


@database_sync_to_async  # type: ignore[misc]
def get_progress_snapshot(*, shop_id: Any) -> dict[str, Any] | None:
    """Return the current progress snapshot for a shop, or None.

    Reads from Redis key sync:progress:{shop_id} via the sync helper
    in apps.reviews.services.progress.read_progress_snapshot.

    Returns None if Redis is unavailable (e.g. in tests with locmem cache).
    """
    from apps.reviews.services.progress import read_progress_snapshot

    try:
        return read_progress_snapshot(shop_id=int(shop_id))
    except (TypeError, ValueError):
        return None
    except NotImplementedError:
        # Cache backend does not support direct Redis connections (e.g. test environment).
        return None
