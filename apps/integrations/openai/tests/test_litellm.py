from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from apps.integrations.openai.litellm import (
    LiteLLMFetchError,
    fetch_litellm_catalog,
    to_per_1m,
)


def _transport(payload=None, *, status=200, content=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if content is not None:
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def test_converts_per_token_to_per_1m():
    assert to_per_1m(0.00000015) == Decimal("0.15000000")
    assert to_per_1m("0.0000006") == Decimal("0.60000000")


@pytest.mark.parametrize("bad", [True, False, None, "abc", -0.1, float("nan"), float("inf"), []])
def test_to_per_1m_rejects_unusable_values(bad):
    with pytest.raises(ValueError, match="price"):
        to_per_1m(bad)


def test_parses_catalog_with_cached_default_zero():
    catalog = fetch_litellm_catalog(
        transport=_transport(
            {
                "m1": {"input_cost_per_token": 1e-7, "output_cost_per_token": 4e-7},
                "m2": {
                    "input_cost_per_token": 1e-6,
                    "output_cost_per_token": 2e-6,
                    "cache_read_input_token_cost": 5e-7,
                },
            }
        )
    )
    assert catalog.prices["m1"].cached_per_1m == Decimal("0")
    assert catalog.prices["m1"].input_per_1m == Decimal("0.10000000")
    assert catalog.prices["m2"].cached_per_1m == Decimal("0.50000000")
    assert catalog.unusable == frozenset()


def test_entry_missing_output_cost_is_unusable():
    catalog = fetch_litellm_catalog(
        transport=_transport(
            {
                "no-out": {"input_cost_per_token": 1e-7},
                "bool-price": {"input_cost_per_token": True, "output_cost_per_token": 1e-7},
            }
        )
    )
    assert catalog.unusable == frozenset({"no-out", "bool-price"})
    assert catalog.prices == {}


def test_non_object_entries_ignored():
    catalog = fetch_litellm_catalog(
        transport=_transport(
            {
                "sample_spec": "text",
                "n": 3,
                "l": [1],
                "ok": {"input_cost_per_token": 1e-7, "output_cost_per_token": 1e-7},
            }
        )
    )
    assert set(catalog.prices) == {"ok"}
    assert catalog.unusable == frozenset()


@pytest.mark.parametrize("bad_cache", ["abc", -1, True])
def test_malformed_cache_price_makes_entry_unusable(bad_cache):
    catalog = fetch_litellm_catalog(
        transport=_transport(
            {
                "m": {
                    "input_cost_per_token": 1e-7,
                    "output_cost_per_token": 1e-7,
                    "cache_read_input_token_cost": bad_cache,
                }
            }
        )
    )
    assert catalog.unusable == frozenset({"m"})
    assert catalog.prices == {}


def test_redirect_is_not_followed():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://evil.test/x"})
    )
    with pytest.raises(LiteLLMFetchError) as info:
        fetch_litellm_catalog(transport=transport)
    assert str(info.value) == "LiteLLM returned HTTP 302"


def _raise(exc):
    def handler(request):
        raise exc

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    ("transport", "message"),
    [
        (_transport(status=500, content=b"secret body"), "LiteLLM returned HTTP 500"),
        (_transport(content=b"<html>nope</html>"), "LiteLLM response was not valid JSON"),
        (_transport([1, 2]), "LiteLLM response had an unexpected shape"),
        (_raise(httpx.ReadTimeout("slow")), "LiteLLM request timed out after 15s"),
        (_raise(httpx.ConnectError("boom")), "Could not reach LiteLLM: ConnectError"),
    ],
)
def test_fetch_failures_raise_fetch_error(transport, message):
    with pytest.raises(LiteLLMFetchError) as info:
        fetch_litellm_catalog(transport=transport)
    assert str(info.value) == message
    assert "secret" not in str(info.value)


def test_uses_configured_url_and_timeout(settings):
    settings.AI_PRICING_SYNC_SOURCE_URL = "https://example.test/prices.json"
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json={})

    fetch_litellm_catalog(transport=httpx.MockTransport(handler))
    assert seen["url"] == "https://example.test/prices.json"
    assert seen["timeout"]["read"] == 15.0


@pytest.mark.parametrize(
    "url", ["http://example.test/prices.json", "ftp://example.test/p", "example.test/p"]
)
def test_non_https_url_rejected_before_any_request(url):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(LiteLLMFetchError) as info:
        fetch_litellm_catalog(url=url, transport=httpx.MockTransport(handler))
    assert str(info.value) == "LiteLLM URL must use https"
    assert calls == []


def test_oversized_response_rejected(monkeypatch):
    from apps.integrations.openai import litellm

    monkeypatch.setattr(litellm, "MAX_RESPONSE_BYTES", 1024)
    with pytest.raises(LiteLLMFetchError) as info:
        fetch_litellm_catalog(transport=_transport(content=b"{" + b" " * 2048 + b"}"))
    assert str(info.value) == "LiteLLM response too large"


def test_response_at_the_cap_is_accepted(monkeypatch):
    from apps.integrations.openai import litellm

    body = b'{"m": {"input_cost_per_token": 1e-7, "output_cost_per_token": 2e-7}}'
    monkeypatch.setattr(litellm, "MAX_RESPONSE_BYTES", len(body))
    catalog = fetch_litellm_catalog(transport=_transport(content=body))
    assert set(catalog.prices) == {"m"}


def test_default_cap_is_20_mb():
    from apps.integrations.openai import litellm

    assert litellm.MAX_RESPONSE_BYTES == 20 * 1024 * 1024


def test_test_settings_point_at_an_unroutable_host(settings):
    assert settings.AI_PRICING_SYNC_SOURCE_URL == "https://litellm.invalid/prices.json"
