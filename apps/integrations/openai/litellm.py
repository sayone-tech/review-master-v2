"""Client for LiteLLM's public model price catalog (Phase 36).

Fetches the JSON and converts per-token prices into per-1M-token Decimals.
Never logs or surfaces response content.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_PER_1M = Decimal(1_000_000)
_QUANT = Decimal("0.00000001")


class LiteLLMFetchError(Exception):
    """The LiteLLM catalog could not be fetched or parsed (message is Superadmin-safe)."""


@dataclass(frozen=True)
class LiteLLMPrice:
    input_per_1m: Decimal
    output_per_1m: Decimal
    cached_per_1m: Decimal


@dataclass(frozen=True)
class LiteLLMCatalog:
    prices: dict[str, LiteLLMPrice]
    unusable: frozenset[str]


def to_per_1m(value: object) -> Decimal:
    """Convert a per-token price to a per-1M-token Decimal quantized to 8 dp."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError("price must be numeric")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("price must be numeric") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("price must be a finite, non-negative number")
    try:
        return (amount * _PER_1M).quantize(_QUANT)
    except InvalidOperation as exc:
        raise ValueError("price out of range") from exc


def _parse_entry(entry: dict[str, Any]) -> LiteLLMPrice | None:
    try:
        input_1m = to_per_1m(entry.get("input_cost_per_token"))
        output_1m = to_per_1m(entry.get("output_cost_per_token"))
    except ValueError:
        return None
    cached_raw = entry.get("cache_read_input_token_cost")
    try:
        cached_1m = to_per_1m(cached_raw) if cached_raw is not None else Decimal(0).quantize(_QUANT)
    except ValueError:
        cached_1m = Decimal(0).quantize(_QUANT)
    return LiteLLMPrice(input_per_1m=input_1m, output_per_1m=output_1m, cached_per_1m=cached_1m)


def fetch_litellm_catalog(
    *,
    url: str | None = None,
    timeout: float = 15.0,
    transport: httpx.BaseTransport | None = None,
) -> LiteLLMCatalog:
    target = url or settings.AI_PRICING_SYNC_SOURCE_URL
    try:
        with httpx.Client(transport=transport, timeout=timeout, follow_redirects=True) as client:
            response = client.get(target)
    except httpx.TimeoutException as exc:
        raise LiteLLMFetchError(f"LiteLLM request timed out after {timeout:g}s") from exc
    except httpx.HTTPError as exc:
        raise LiteLLMFetchError(f"Could not reach LiteLLM: {type(exc).__name__}") from exc

    if response.status_code != 200:
        raise LiteLLMFetchError(f"LiteLLM returned HTTP {response.status_code}")
    try:
        payload = json.loads(response.content)
    except ValueError as exc:
        raise LiteLLMFetchError("LiteLLM response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise LiteLLMFetchError("LiteLLM response had an unexpected shape")

    prices: dict[str, LiteLLMPrice] = {}
    unusable: set[str] = set()
    for key, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        price = _parse_entry(entry)
        if price is None:
            unusable.add(key)
        else:
            prices[key] = price
    return LiteLLMCatalog(prices=prices, unusable=frozenset(unusable))
