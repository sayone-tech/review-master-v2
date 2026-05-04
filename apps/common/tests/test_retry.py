"""INFRA-05 + INFRA-11: with_retry decorator — exhaustion, recovery, defaults."""

import pytest
from tenacity import stop_after_attempt, wait_exponential

from apps.common.retry import with_retry


def test_retry_exhaustion_raises() -> None:
    call_count = 0

    @with_retry(max_attempts=3, wait_min=0.001, wait_max=0.001)
    def always_fails() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("deliberate failure")

    with pytest.raises(ValueError, match="deliberate failure"):
        always_fails()

    assert call_count == 3


def test_retry_succeeds_on_third_attempt() -> None:
    call_count = 0

    @with_retry(max_attempts=3, wait_min=0.001, wait_max=0.001)
    def fails_twice_then_succeeds() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient")
        return "ok"

    assert fails_twice_then_succeeds() == "ok"
    assert call_count == 3


def test_retry_returns_value_on_first_success() -> None:
    call_count = 0

    @with_retry(max_attempts=3, wait_min=0.001, wait_max=0.001)
    def succeeds_immediately() -> int:
        nonlocal call_count
        call_count += 1
        return 42

    assert succeeds_immediately() == 42
    assert call_count == 1


def test_retry_no_retry_on_non_matching_exception() -> None:
    call_count = 0

    @with_retry(
        max_attempts=3,
        wait_min=0.001,
        wait_max=0.001,
        retry_on=(ValueError,),
    )
    def raises_type_error() -> None:
        nonlocal call_count
        call_count += 1
        raise TypeError("not retryable")

    with pytest.raises(TypeError, match="not retryable"):
        raises_type_error()

    assert call_count == 1


def test_retry_default_max_attempts_is_3() -> None:
    """INFRA-05: 3 retries (i.e. 3 total attempts)."""
    call_count = 0

    @with_retry(wait_min=0.001, wait_max=0.001)
    def always_fails() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("x")

    with pytest.raises(ValueError, match="x"):
        always_fails()
    assert call_count == 3


def test_retry_default_wait_min_is_30_seconds() -> None:
    """INFRA-05: base delay 30 seconds. Verified via tenacity wait introspection."""

    @with_retry()
    def stub() -> None:
        pass

    wait_strategy = stub.retry.wait  # type: ignore[attr-defined]
    assert isinstance(wait_strategy, wait_exponential)
    assert wait_strategy.min == 30


def test_retry_default_wait_max_is_600_seconds() -> None:
    """INFRA-05: max delay 600 seconds (10 minutes). Verified via introspection."""

    @with_retry()
    def stub() -> None:
        pass

    wait_strategy = stub.retry.wait  # type: ignore[attr-defined]
    assert isinstance(wait_strategy, wait_exponential)
    assert wait_strategy.max == 600


def test_retry_default_stop_strategy() -> None:
    """INFRA-05: stop_after_attempt(3) is the default."""

    @with_retry()
    def stub() -> None:
        pass

    stop_strategy = stub.retry.stop  # type: ignore[attr-defined]
    assert isinstance(stop_strategy, stop_after_attempt)
    assert stop_strategy.max_attempt_number == 3
