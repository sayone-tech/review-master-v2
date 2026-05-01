"""Tenacity-backed exponential-backoff retry decorator.

See CLAUDE.md §12.3 for Celery task retry semantics — this helper provides
the same contract for non-Celery code paths (e.g. service functions called
directly from views or management commands).

INFRA-05 spec: 3 retries, base delay 30s, max delay 10 min (600s), exponential.
INFRA-11 spec: a deliberately-failing task wrapped with this decorator must
retry 3 times before the exception escapes.

Example:
    from apps.common.retry import with_retry

    @with_retry(max_attempts=3, wait_min=30, wait_max=600)
    def call_external_api() -> dict:
        response = httpx.get("https://example.com/api")
        response.raise_for_status()
        return response.json()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def with_retry(
    *,
    max_attempts: int = 3,
    wait_min: float = 30,
    wait_max: float = 600,
    reraise: bool = True,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[..., Any]:
    """Build an exponential-backoff retry decorator.

    Args:
        max_attempts: Total attempts (including the first call). Default 3.
        wait_min: Minimum wait between retries, in seconds. Default 30.
        wait_max: Maximum wait between retries, in seconds. Default 600 (10 min).
        reraise: If True (default), the original exception is raised after
                 exhaustion (NOT a tenacity RetryError).
        retry_on: Tuple of exception classes to retry on. Default (Exception,).

    Returns:
        A decorator that wraps the target callable.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(retry_on),
        reraise=reraise,
    )
