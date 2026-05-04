"""Phase 11 — Sync progress state in Redis + Google API token bucket.

Keys (per CLAUDE.md §7.7):
    sync:progress:{shop_id}         — JSON snapshot of progress, TTLs vary by status
    rate:google:project             — global token bucket counter, 60-second window

Snapshot schema (written by sync service, read by SyncProgressConsumer):
    {
      "shop_id": int,
      "status": "fetching" | "enriching" | "success" | "failed",
      "fetched": int,
      "total_estimate": int | None,
      "enriched": int,
      "started_at": ISO timestamp,
      "last_update_at": ISO timestamp,
      "duration_seconds": int | None,
      "error_code": str | None,
      "error_message": str | None,
      "page_count": int,         # used for ETA calculation (PROG-02 needs >=2)
    }
"""

from __future__ import annotations

import json
from typing import Any

from django_redis import get_redis_connection

PROGRESS_KEY_TMPL = "sync:progress:{shop_id}"
ENRICHED_COUNTER_KEY_TMPL = "sync:enriched:{shop_id}"
TTL_ACTIVE_SECONDS = 86400  # 24h while running
TTL_SUCCESS_SECONDS = 3600  # 1h after success
TTL_FAILED_SECONDS = 604800  # 7d after permanent failure

GOOGLE_BUCKET_KEY = "rate:google:project"
GOOGLE_BUCKET_WINDOW_SECONDS = 60
GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE = 600  # defensive ceiling — adjust per CLAUDE.md §7.7


def _ttl_for_status(status: str) -> int:
    if status == "success":
        return TTL_SUCCESS_SECONDS
    if status == "failed":
        return TTL_FAILED_SECONDS
    return TTL_ACTIVE_SECONDS


def write_progress_snapshot(*, shop_id: int, data: dict[str, Any]) -> None:
    """Write the snapshot under sync:progress:{shop_id} with status-aware TTL.

    The data dict MUST include a "status" key. Caller controls all other fields.
    """
    status = str(data.get("status", "fetching"))
    ttl = _ttl_for_status(status)
    conn = get_redis_connection("default")
    conn.setex(PROGRESS_KEY_TMPL.format(shop_id=shop_id), ttl, json.dumps(data))


def read_progress_snapshot(*, shop_id: int) -> dict[str, Any] | None:
    """Read snapshot. Returns None when key absent."""
    conn = get_redis_connection("default")
    raw = conn.get(PROGRESS_KEY_TMPL.format(shop_id=shop_id))
    if raw is None:
        return None
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None
    except (TypeError, ValueError):
        return None


def clear_progress_snapshot(*, shop_id: int) -> None:
    """Delete the progress key and enriched counter (used when starting a fresh sync)."""
    conn = get_redis_connection("default")
    conn.delete(
        PROGRESS_KEY_TMPL.format(shop_id=shop_id),
        ENRICHED_COUNTER_KEY_TMPL.format(shop_id=shop_id),
    )


def increment_enriched_counter(*, shop_id: int) -> int:
    """Atomically increment the enriched counter and return the new value.

    Uses Redis INCR so concurrent workers never lose increments (unlike the
    read-modify-write pattern on the JSON snapshot). TTL mirrors the active
    snapshot TTL; the key is reset when clear_progress_snapshot is called.
    """
    conn = get_redis_connection("default")
    key = ENRICHED_COUNTER_KEY_TMPL.format(shop_id=shop_id)
    pipe = conn.pipeline()
    pipe.incr(key)
    pipe.expire(key, TTL_ACTIVE_SECONDS)
    new_value, _ = pipe.execute()
    return int(new_value)


def increment_google_token_bucket(*, count: int = 1) -> int:
    """Increment the global Google API counter; refresh expiry to 60s window.

    Returns the new counter value.
    """
    conn = get_redis_connection("default")
    pipe = conn.pipeline()
    pipe.incrby(GOOGLE_BUCKET_KEY, count)
    pipe.expire(GOOGLE_BUCKET_KEY, GOOGLE_BUCKET_WINDOW_SECONDS)
    new_value, _ = pipe.execute()
    return int(new_value)


def token_bucket_depleted(*, max_calls: int = GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE) -> bool:
    """Return True when the rolling 60-second counter is at/above the cap."""
    conn = get_redis_connection("default")
    raw = conn.get(GOOGLE_BUCKET_KEY)
    if raw is None:
        return False
    try:
        return int(raw) >= max_calls
    except (TypeError, ValueError):
        return False
