"""Phase 11 — Tests for progress snapshot + token bucket service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.reviews.services.progress import (
    GOOGLE_BUCKET_KEY,
    GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE,
    PROGRESS_KEY_TMPL,
    TTL_ACTIVE_SECONDS,
    TTL_FAILED_SECONDS,
    TTL_SUCCESS_SECONDS,
    clear_progress_snapshot,
    increment_google_token_bucket,
    read_progress_snapshot,
    token_bucket_depleted,
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

    def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if existed else 0

    def pipeline(self):  # type: ignore[no-untyped-def]
        commands: list = []
        outer = self

        class _Pipe:
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
def fake_redis():
    fake = _FakeRedis()
    with patch(
        "apps.reviews.services.progress.get_redis_connection",
        return_value=fake,
    ):
        yield fake


def test_write_progress_snapshot_default_ttl_is_24h(fake_redis: _FakeRedis) -> None:
    write_progress_snapshot(shop_id=1, data={"status": "fetching", "fetched": 5})
    key = PROGRESS_KEY_TMPL.format(shop_id=1)
    assert fake_redis.ttls[key] == TTL_ACTIVE_SECONDS


def test_write_progress_snapshot_success_ttl_is_1h(fake_redis: _FakeRedis) -> None:
    write_progress_snapshot(shop_id=1, data={"status": "success", "fetched": 5})
    assert fake_redis.ttls[PROGRESS_KEY_TMPL.format(shop_id=1)] == TTL_SUCCESS_SECONDS


def test_write_progress_snapshot_failed_ttl_is_7d(fake_redis: _FakeRedis) -> None:
    write_progress_snapshot(shop_id=1, data={"status": "failed", "error_code": "x"})
    assert fake_redis.ttls[PROGRESS_KEY_TMPL.format(shop_id=1)] == TTL_FAILED_SECONDS


def test_read_progress_snapshot_returns_dict(fake_redis: _FakeRedis) -> None:
    write_progress_snapshot(shop_id=2, data={"status": "fetching", "fetched": 10})
    snap = read_progress_snapshot(shop_id=2)
    assert snap is not None
    assert snap["fetched"] == 10
    assert snap["status"] == "fetching"


def test_read_progress_snapshot_missing_returns_none(fake_redis: _FakeRedis) -> None:
    assert read_progress_snapshot(shop_id=999) is None


def test_clear_progress_snapshot_deletes_key(fake_redis: _FakeRedis) -> None:
    write_progress_snapshot(shop_id=3, data={"status": "fetching"})
    clear_progress_snapshot(shop_id=3)
    assert read_progress_snapshot(shop_id=3) is None


def test_token_bucket_increment(fake_redis: _FakeRedis) -> None:
    assert increment_google_token_bucket() == 1
    assert increment_google_token_bucket() == 2
    assert fake_redis.store[GOOGLE_BUCKET_KEY] == b"2"


def test_token_bucket_depleted_when_at_cap(fake_redis: _FakeRedis) -> None:
    fake_redis.store[GOOGLE_BUCKET_KEY] = str(GOOGLE_BUCKET_MAX_CALLS_PER_MINUTE).encode()
    assert token_bucket_depleted() is True


def test_token_bucket_not_depleted_below_cap(fake_redis: _FakeRedis) -> None:
    fake_redis.store[GOOGLE_BUCKET_KEY] = b"5"
    assert token_bucket_depleted() is False
