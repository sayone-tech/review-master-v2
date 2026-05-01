"""INFRA-10: distributed_lock context manager — acquire/release/contention/TTL."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import redis

from apps.common.locks import distributed_lock


def test_lock_acquired_when_free() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key") as acquired,
    ):
        assert acquired is True

    mock_lock.release.assert_called_once()


def test_lock_not_acquired_when_held() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = False
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key") as acquired,
    ):
        assert acquired is False

    mock_lock.release.assert_not_called()


def test_lock_release_swallows_lock_not_owned_error() -> None:
    """If TTL expires before release, redis-py raises LockNotOwnedError.

    The helper must swallow this — the lock is already gone; nothing to free.
    """
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_lock.release.side_effect = redis.exceptions.LockNotOwnedError("expired")
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    # Must NOT raise.
    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key") as acquired,
    ):
        assert acquired is True


def test_lock_uses_default_timeout_300() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key"),
    ):
        pass

    mock_conn.lock.assert_called_once_with("test:lock:key", timeout=300)


def test_lock_blocking_default_false() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key"),
    ):
        pass

    mock_lock.acquire.assert_called_once_with(blocking=False)


def test_lock_explicit_timeout_passed_through() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key", timeout=30),
    ):
        pass

    mock_conn.lock.assert_called_once_with("test:lock:key", timeout=30)


def test_lock_blocking_true_passes_through() -> None:
    mock_lock = MagicMock()
    mock_lock.acquire.return_value = True
    mock_conn = MagicMock()
    mock_conn.lock.return_value = mock_lock

    with (
        patch("apps.common.locks.get_redis_connection", return_value=mock_conn),
        distributed_lock("test:lock:key", blocking=True),
    ):
        pass

    mock_lock.acquire.assert_called_once_with(blocking=True)
