"""Phase 23 — Tests for OpenAI token bucket + _wait_for_openai_token + per-phase counters.

Wave 0 module — tests the new additions to apps/reviews/services/progress.py:
- increment_openai_token_bucket
- openai_token_bucket_depleted
- _wait_for_openai_token (seed-path WAIT helper — never raises)
- increment_vocab_counter
- increment_bulk_counter
- clear_progress_snapshot extended to clean new vocab/bulk counter keys
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.reviews.services.progress import (
    BULK_COUNTER_KEY_TMPL,
    OPENAI_BUCKET_KEY_TMPL,
    OPENAI_BUCKET_WINDOW_SECONDS,
    PROGRESS_KEY_TMPL,
    TTL_ACTIVE_SECONDS,
    VOCAB_COUNTER_KEY_TMPL,
    _wait_for_openai_token,
    clear_progress_snapshot,
    increment_bulk_counter,
    increment_openai_token_bucket,
    increment_vocab_counter,
    openai_token_bucket_depleted,
    write_progress_snapshot,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value.encode() if isinstance(value, str) else value
        self.ttls[key] = ttl

    def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self.store:
                self.store.pop(key, None)
                self.ttls.pop(key, None)
                count += 1
        return count

    def pipeline(self):  # type: ignore[no-untyped-def]
        commands: list = []
        outer = self

        class _Pipe:
            def incr(self, key: str):  # type: ignore[no-untyped-def]
                commands.append(("incrby", key, 1))
                return self

            def incrby(self, key: str, n: int):  # type: ignore[no-untyped-def]
                commands.append(("incrby", key, n))
                return self

            def expire(self, key: str, ttl: int):  # type: ignore[no-untyped-def]
                commands.append(("expire", key, ttl))
                return self

            def execute(self):  # type: ignore[no-untyped-def]
                results = []
                for name, key, n in commands:
                    if name == "incrby":
                        cur = int(outer.store.get(key, b"0") or b"0")
                        cur += n
                        outer.store[key] = str(cur).encode()
                        results.append(cur)
                    elif name == "expire":
                        outer.ttls[key] = n
                        results.append(True)
                return results

        return _Pipe()


@pytest.fixture
def fake_redis():  # type: ignore[no-untyped-def]
    fake = _FakeRedis()
    with patch(
        "apps.reviews.services.progress.get_redis_connection",
        return_value=fake,
    ):
        yield fake


# ---------------------------------------------------------------------------
# increment_openai_token_bucket
# ---------------------------------------------------------------------------


def test_increment_openai_bucket_returns_new_value(fake_redis: _FakeRedis) -> None:
    """First call returns 1, second returns 2 — sequential INCR."""
    assert increment_openai_token_bucket(organisation_id=1) == 1
    assert increment_openai_token_bucket(organisation_id=1) == 2


def test_increment_openai_bucket_sets_ttl(fake_redis: _FakeRedis) -> None:
    """TTL on the bucket key must equal OPENAI_BUCKET_WINDOW_SECONDS (60s)."""
    increment_openai_token_bucket(organisation_id=5)
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=5)
    assert fake_redis.ttls[key] == OPENAI_BUCKET_WINDOW_SECONDS


def test_increment_openai_bucket_isolated_per_org(fake_redis: _FakeRedis) -> None:
    """Different organisation IDs use different bucket keys (T-23-01 cross-tenant isolation)."""
    increment_openai_token_bucket(organisation_id=10)
    increment_openai_token_bucket(organisation_id=10)
    increment_openai_token_bucket(organisation_id=20)
    key_10 = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=10)
    key_20 = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=20)
    assert int(fake_redis.store[key_10]) == 2
    assert int(fake_redis.store[key_20]) == 1


# ---------------------------------------------------------------------------
# openai_token_bucket_depleted
# ---------------------------------------------------------------------------


def test_openai_bucket_not_depleted_when_absent(fake_redis: _FakeRedis) -> None:
    """Absent key → False (bucket is fresh, not depleted)."""
    assert openai_token_bucket_depleted(organisation_id=99, max_calls=500) is False


def test_openai_bucket_depleted_at_max_calls(fake_redis: _FakeRedis) -> None:
    """Counter equal to max_calls → depleted."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=7)
    fake_redis.store[key] = b"500"
    assert openai_token_bucket_depleted(organisation_id=7, max_calls=500) is True


def test_openai_bucket_depleted_above_max_calls(fake_redis: _FakeRedis) -> None:
    """Counter above max_calls → depleted (overage tolerated per Pitfall 5)."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=7)
    fake_redis.store[key] = b"600"
    assert openai_token_bucket_depleted(organisation_id=7, max_calls=500) is True


def test_openai_bucket_not_depleted_below_max_calls(fake_redis: _FakeRedis) -> None:
    """Counter below max_calls → not depleted."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=7)
    fake_redis.store[key] = b"499"
    assert openai_token_bucket_depleted(organisation_id=7, max_calls=500) is False


# ---------------------------------------------------------------------------
# _wait_for_openai_token — seed-path WAIT helper (never raises)
# ---------------------------------------------------------------------------


def test_wait_for_openai_token_returns_immediately_when_headroom(
    fake_redis: _FakeRedis,
) -> None:
    """When bucket is not depleted, acquires token immediately (no sleep) and returns count."""
    # bucket is empty (not depleted)
    with patch("time.sleep") as mock_sleep:
        result = _wait_for_openai_token(organisation_id=1, max_calls=500)
    mock_sleep.assert_not_called()
    assert result == 1  # incremented exactly once


def test_wait_for_openai_token_increments_exactly_once(fake_redis: _FakeRedis) -> None:
    """Only one increment call regardless of wait iterations."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=2)
    fake_redis.store[key] = b"0"
    with patch("time.sleep"):
        _wait_for_openai_token(organisation_id=2, max_calls=500)
    assert int(fake_redis.store[key]) == 1


def test_wait_for_openai_token_waits_then_acquires_when_bucket_frees(
    fake_redis: _FakeRedis,
) -> None:
    """Bucket starts depleted; after one sleep call the bucket 'frees' and the helper returns."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=3)
    fake_redis.store[key] = b"500"  # starts depleted

    call_count = [0]

    def _fake_sleep(seconds: float) -> None:
        call_count[0] += 1
        # Simulate bucket freeing up after first sleep
        if call_count[0] >= 1:
            fake_redis.store[key] = b"0"  # now below max_calls

    with patch("time.sleep", side_effect=_fake_sleep):
        result = _wait_for_openai_token(organisation_id=3, max_calls=500)

    assert call_count[0] == 1  # slept exactly once
    assert result == 1  # acquired token


def test_wait_for_openai_token_never_raises_when_still_depleted(
    fake_redis: _FakeRedis,
) -> None:
    """If bucket remains depleted until max_wait_seconds elapses, must NOT raise.
    Returns the incremented count (tolerated overage per Pitfall 5 / T-23-12).
    """
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=4)
    fake_redis.store[key] = b"500"  # permanently depleted during test

    with patch("time.sleep"):
        # max_wait_seconds very small (0.01) so we exhaust quickly
        result = _wait_for_openai_token(
            organisation_id=4,
            max_calls=500,
            max_wait_seconds=0.01,
            sleep_seconds=10.0,  # large enough to skip all sleep iterations
        )
    # Must return a value (not raise) — tolerated overage
    assert isinstance(result, int)
    assert result >= 1


def test_wait_for_openai_token_runs_fast_with_patched_sleep(
    fake_redis: _FakeRedis,
) -> None:
    """Patching time.sleep ensures the wait loop completes without real blocking."""
    key = OPENAI_BUCKET_KEY_TMPL.format(organisation_id=6)
    fake_redis.store[key] = b"500"

    sleep_calls: list[float] = []
    with patch("time.sleep", side_effect=sleep_calls.append):
        _wait_for_openai_token(
            organisation_id=6,
            max_calls=500,
            max_wait_seconds=0.5,
            sleep_seconds=0.1,
        )
    # Did not raise — test passes


# ---------------------------------------------------------------------------
# increment_vocab_counter / increment_bulk_counter
# ---------------------------------------------------------------------------


def test_increment_vocab_counter_returns_new_value(fake_redis: _FakeRedis) -> None:
    """Vocab counter increments and returns new value."""
    assert increment_vocab_counter(shop_id=10) == 1
    assert increment_vocab_counter(shop_id=10) == 2


def test_increment_vocab_counter_sets_ttl(fake_redis: _FakeRedis) -> None:
    """Vocab counter key gets active TTL (24h)."""
    increment_vocab_counter(shop_id=11)
    key = VOCAB_COUNTER_KEY_TMPL.format(shop_id=11)
    assert fake_redis.ttls[key] == TTL_ACTIVE_SECONDS


def test_increment_bulk_counter_returns_new_value(fake_redis: _FakeRedis) -> None:
    """Bulk counter increments and returns new value."""
    assert increment_bulk_counter(shop_id=20) == 1
    assert increment_bulk_counter(shop_id=20) == 2


def test_increment_bulk_counter_sets_ttl(fake_redis: _FakeRedis) -> None:
    """Bulk counter key gets active TTL (24h)."""
    increment_bulk_counter(shop_id=21)
    key = BULK_COUNTER_KEY_TMPL.format(shop_id=21)
    assert fake_redis.ttls[key] == TTL_ACTIVE_SECONDS


# ---------------------------------------------------------------------------
# clear_progress_snapshot extended to clean vocab/bulk keys
# ---------------------------------------------------------------------------


def test_clear_progress_snapshot_deletes_vocab_counter(fake_redis: _FakeRedis) -> None:
    """clear_progress_snapshot removes sync:vocab:{shop_id} key."""
    write_progress_snapshot(shop_id=30, data={"status": "fetching"})
    increment_vocab_counter(shop_id=30)
    clear_progress_snapshot(shop_id=30)
    vocab_key = VOCAB_COUNTER_KEY_TMPL.format(shop_id=30)
    assert vocab_key not in fake_redis.store


def test_clear_progress_snapshot_deletes_bulk_counter(fake_redis: _FakeRedis) -> None:
    """clear_progress_snapshot removes sync:bulk:{shop_id} key."""
    write_progress_snapshot(shop_id=31, data={"status": "fetching"})
    increment_bulk_counter(shop_id=31)
    clear_progress_snapshot(shop_id=31)
    bulk_key = BULK_COUNTER_KEY_TMPL.format(shop_id=31)
    assert bulk_key not in fake_redis.store


def test_clear_progress_snapshot_deletes_all_new_keys(fake_redis: _FakeRedis) -> None:
    """clear_progress_snapshot cleans progress, vocab, and bulk keys together."""
    write_progress_snapshot(shop_id=32, data={"status": "fetching"})
    increment_vocab_counter(shop_id=32)
    increment_bulk_counter(shop_id=32)
    clear_progress_snapshot(shop_id=32)

    progress_key = PROGRESS_KEY_TMPL.format(shop_id=32)
    vocab_key = VOCAB_COUNTER_KEY_TMPL.format(shop_id=32)
    bulk_key = BULK_COUNTER_KEY_TMPL.format(shop_id=32)
    assert progress_key not in fake_redis.store
    assert vocab_key not in fake_redis.store
    assert bulk_key not in fake_redis.store
