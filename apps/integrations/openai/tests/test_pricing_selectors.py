"""Phase 35 task 2 - pricing selectors and missing-price detection."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.integrations.openai.models import AiPricing
from apps.integrations.openai.selectors.pricing import (
    MISSING_CACHE_KEY,
    invalidate_missing_pricing_cache,
    list_missing_pricing_models,
    list_model_suggestions,
    list_price_history,
    list_price_summary,
)
from apps.integrations.openai.tests.factories import AiPricingFactory, AiUsageLogFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated(settings):
    """Drop migration-seeded prices and pin the configured model."""
    AiPricing.objects.all().delete()
    settings.OPENAI_MODEL = "configured-model"
    AiPricingFactory(model="configured-model", effective_from=timezone.now() - timedelta(days=5))


def _price(model, **kw):
    kw.setdefault("effective_from", timezone.now() - timedelta(days=5))
    return AiPricingFactory(model=model, **kw)


def _use(model, days_ago=1):
    return AiUsageLogFactory(model=model, created_at=timezone.now() - timedelta(days=days_ago))


def test_all_priced_returns_empty():
    _price("m1")
    _use("m1")
    assert list_missing_pricing_models(use_cache=False) == []


def test_logged_unpriced_model_is_listed_with_last_used():
    _use("m2", days_ago=3)
    last = _use("m2", days_ago=1).created_at
    assert list_missing_pricing_models(use_cache=False) == [
        {"model": "m2", "last_used_at": last, "configured": False}
    ]


def test_known_free_models_excluded(settings):
    settings.AI_PRICING_KNOWN_FREE_MODELS = ["free-m"]
    _use("free-m")
    assert list_missing_pricing_models(use_cache=False) == []


def test_lookback_window_boundary(settings):
    settings.AI_PRICING_LOOKBACK_DAYS = 90
    _use("recent", days_ago=89)
    _use("old", days_ago=91)
    assert [m["model"] for m in list_missing_pricing_models(use_cache=False)] == ["recent"]


def test_configured_model_listed_even_without_usage(settings):
    AiPricing.objects.all().delete()
    settings.OPENAI_MODEL = "gpt-new"
    assert list_missing_pricing_models(use_cache=False) == [
        {"model": "gpt-new", "last_used_at": None, "configured": True}
    ]


def test_model_with_only_scheduled_price_counts_as_missing():
    _price("sched", effective_from=timezone.now() + timedelta(days=2))
    _use("sched")
    assert [m["model"] for m in list_missing_pricing_models(use_cache=False)] == ["sched"]


def test_missing_ordered_by_last_used_desc_none_last():
    AiPricing.objects.all().delete()
    _use("older", days_ago=5)
    _use("newer", days_ago=1)
    assert [m["model"] for m in list_missing_pricing_models(use_cache=False)] == [
        "newer",
        "older",
        "configured-model",
    ]


def test_missing_result_is_cached_and_invalidated():
    _use("m3")
    first = list_missing_pricing_models()
    assert cache.get(MISSING_CACHE_KEY) == first
    with CaptureQueriesContext(connection) as ctx:
        assert list_missing_pricing_models() == first
    assert len(ctx.captured_queries) == 0
    _price("m3")
    invalidate_missing_pricing_cache()
    assert list_missing_pricing_models() == []


def test_price_summary_current_and_scheduled():
    now = timezone.now()
    start = now + timedelta(days=2)
    old = _price("a", effective_from=now - timedelta(days=9), effective_to=now - timedelta(days=4))
    cur = _price("a", effective_from=now - timedelta(days=4), effective_to=start)
    nxt = _price("a", effective_from=start)
    only_sched = _price("b", effective_from=now + timedelta(days=1))
    assert old.pk  # closed historical row must not appear
    rows = [r for r in list_price_summary(now=now) if r["model"] in {"a", "b"}]
    assert [(r["model"], r["current"], r["scheduled"]) for r in rows] == [
        ("a", cur, nxt),
        ("b", None, only_sched),
    ]


def test_history_chronological():
    now = timezone.now()
    r2 = _price("h", effective_from=now - timedelta(days=2), effective_to=now - timedelta(days=1))
    r1 = _price("h", effective_from=now - timedelta(days=9), effective_to=now - timedelta(days=2))
    r3 = _price("h", effective_from=now - timedelta(days=1))
    _price("other")
    assert list(list_price_history(model="h")) == [r1, r2, r3]


def test_suggestions_unpriced_first_then_alpha_and_capped():
    _price("zeta")
    _price("alpha")
    _use("unpriced-old", days_ago=5)
    _use("unpriced-new", days_ago=1)
    names = [s["model"] for s in list_model_suggestions()]
    assert names == ["unpriced-new", "unpriced-old", "alpha", "configured-model", "zeta"]
    assert [s["has_price"] for s in list_model_suggestions()] == [False, False, True, True, True]
    assert len(list_model_suggestions(limit=2)) == 2


def test_suggestions_query_is_case_insensitive():
    _price("GPT-Five")
    _price("other")
    assert [s["model"] for s in list_model_suggestions(query="gpt")] == ["GPT-Five"]


def test_pricing_selectors_fixed_query_counts(django_assert_max_num_queries):
    now = timezone.now()
    for i in range(30):
        m = f"model-{i}"
        _price(m, effective_from=now - timedelta(days=9), effective_to=now - timedelta(days=5))
        _price(m, effective_from=now - timedelta(days=5), effective_to=now + timedelta(days=1))
        _price(m, effective_from=now + timedelta(days=1))
        _use(f"used-{i}")
    with django_assert_max_num_queries(1):
        for r in list_price_summary(now=now):
            _ = r["current"].created_by if r["current"] else None
    with django_assert_max_num_queries(1):
        for r in list_price_history(model="model-1"):
            _ = r.created_by
    with django_assert_max_num_queries(3):
        list_model_suggestions(now=now)
    with django_assert_max_num_queries(3):
        list_missing_pricing_models(now=now, use_cache=False)
    list_missing_pricing_models(now=now)
    with django_assert_max_num_queries(0):
        list_missing_pricing_models(now=now)
