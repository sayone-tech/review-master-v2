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

    The full snapshot dict is returned verbatim — no key allowlist or filtering.
    Phase 23 four-step keys are passed through transparently (SEED-01):
      - step: "fetching" | "vocab" | "enriching" | "finalising" | "success" | "failed"
      - vocab_enriched: int — reviews enriched during the seed (vocabulary-building) phase
      - vocab_total: int — total seed-phase reviews
      - finalising_processed: int — canonical-tag groups processed during finalising
      - finalising_total: int — total canonical-tag groups to process

    Returns None if Redis is unavailable (e.g. in tests with locmem cache),
    or if no snapshot exists for this shop.
    """
    from apps.reviews.services.progress import read_progress_snapshot

    try:
        return read_progress_snapshot(shop_id=int(shop_id))
    except (TypeError, ValueError):
        return None
    except NotImplementedError:
        # Cache backend does not support direct Redis connections (e.g. test environment).
        return None
