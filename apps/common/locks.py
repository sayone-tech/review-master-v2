"""Redis distributed lock helper.

See CLAUDE.md §7.6 for interface contract and key conventions.

Use this for any task that must NOT run concurrently for the same entity
(per-shop sync, per-review enrichment, per-review reply submission).

Acquisition is non-blocking by default — if another worker already holds
the lock, the context yields False and the caller exits cleanly. The next
scheduled run of the task picks up the work.

Example:
    from apps.common.locks import distributed_lock

    with distributed_lock(f"lock:google_sync:shop:{shop_id}", timeout=300) as acquired:
        if not acquired:
            return  # another worker holds the lock; exit silently
        _do_sync(shop_id)
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator

import redis
from django_redis import get_redis_connection


@contextlib.contextmanager
def distributed_lock(
    key: str,
    timeout: int = 300,
    blocking: bool = False,
) -> Generator[bool, None, None]:
    """Acquire a Redis distributed lock.

    Args:
        key: Lock key. Use the conventions in CLAUDE.md §7.6
             (e.g. "lock:google_sync:shop:{shop_id}").
        timeout: Lock TTL in seconds. The lock auto-releases if the
                 holder process crashes.
        blocking: If True, wait for the lock; if False (default), return
                  immediately with acquired=False if the lock is held.

    Yields:
        True if the lock was acquired, False if it was not (and blocking=False).
    """
    conn = get_redis_connection("default")
    lock = conn.lock(key, timeout=timeout)
    acquired = lock.acquire(blocking=blocking)
    try:
        yield acquired
    finally:
        if acquired:
            # TTL expired before we got to release → LockNotOwnedError is safe to ignore.
            # Another worker may have legitimately taken the lock after our TTL elapsed.
            with contextlib.suppress(redis.exceptions.LockNotOwnedError):
                lock.release()
