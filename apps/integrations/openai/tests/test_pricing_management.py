"""Phase 35 task 3 - append-only pricing management service."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.cache import cache
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.models import AuditLog
from apps.integrations.openai.models import AiPricing, AiUsageLog
from apps.integrations.openai.selectors.pricing import MISSING_CACHE_KEY
from apps.integrations.openai.services.pricing_management import (
    BackdatedPriceError,
    ConcurrentPriceChangeError,
    ManualPriceProtectedError,
    PriceNotScheduledError,
    ScheduledPriceExistsError,
    add_price,
    delete_scheduled_price,
)
from apps.integrations.openai.tests.factories import AiPricingFactory, AiUsageLogFactory

pytestmark = pytest.mark.django_db

PRICES = {
    "input_token_price_per_1m": Decimal("0.15"),
    "output_token_price_per_1m": Decimal("0.60"),
    "cached_token_price_per_1m": Decimal("0.075"),
}


@pytest.fixture
def actor():
    return UserFactory(role=User.Role.SUPERADMIN)


def _add(actor, now, *, model="m", offset=timedelta(0), **kw):
    return add_price(model=model, effective_from=now + offset, actor=actor, now=now, **PRICES, **kw)


def test_first_price_for_model_creates_open_row_and_audit(actor):
    now = timezone.now()
    row = _add(actor, now)
    assert row.effective_to is None
    assert row.source == AiPricing.Source.MANUAL
    assert row.created_by == actor
    log = AuditLog.objects.get()
    assert log.organisation is None
    assert log.actor == actor
    assert (log.entity_type, log.entity_id, log.action) == (
        "ai_pricing",
        str(row.pk),
        "ai_pricing.added",
    )
    assert log.before_data is None
    assert log.after_data["model"] == "m"
    assert log.after_data["input_token_price_per_1m"] == "0.15000000"
    assert log.after_data["effective_to"] is None
    assert log.after_data["source"] == "manual"


def test_sync_source_and_no_actor_allowed():
    now = timezone.now()
    row = add_price(model="m", effective_from=now, actor=None, source="sync", now=now, **PRICES)
    assert row.source == "sync"
    assert row.created_by is None
    assert AuditLog.objects.get().actor is None


def test_model_is_stripped_and_empty_rejected(actor):
    now = timezone.now()
    assert _add(actor, now, model="  gpt-x ").model == "gpt-x"
    with pytest.raises(ValueError, match="must not be empty"):
        _add(actor, now, model="   ")


def test_new_price_now_closes_current_at_new_start(actor):
    now = timezone.now()
    old = AiPricingFactory(model="m", effective_from=now - timedelta(days=5), effective_to=None)
    new = _add(actor, now)
    old.refresh_from_db()
    assert old.effective_to == new.effective_from
    log = AuditLog.objects.get()
    assert log.before_data["effective_to"] is None
    assert log.before_data["effective_from"] == old.effective_from.isoformat()


def test_scheduled_price_keeps_current_active_until_start(actor):
    now = timezone.now()
    old = AiPricingFactory(model="m", effective_from=now - timedelta(days=5), effective_to=None)
    start = now + timedelta(days=2)
    new = _add(actor, now, offset=timedelta(days=2))
    assert AiPricing.objects.get_active(model="m", at=now) == old
    assert AiPricing.objects.get_active(model="m", at=start) == new


def test_backdated_price_rejected(actor):
    now = timezone.now()
    with pytest.raises(BackdatedPriceError) as exc:
        _add(actor, now, offset=-timedelta(seconds=6))
    assert exc.value.code == "backdated"
    assert exc.value.detail == "Prices cannot start in the past."
    assert not AiPricing.objects.filter(model="m").exists()
    assert not AuditLog.objects.exists()
    _add(actor, now, offset=-timedelta(seconds=4))
    assert AiPricing.objects.filter(model="m").count() == 1


def test_second_scheduled_price_rejected(actor):
    now = timezone.now()
    AiPricingFactory(
        model="m", effective_from=now - timedelta(days=5), effective_to=now + timedelta(days=1)
    )
    sched = AiPricingFactory(model="m", effective_from=now + timedelta(days=1), effective_to=None)
    with pytest.raises(ScheduledPriceExistsError) as exc:
        _add(actor, now, offset=timedelta(days=3))
    assert exc.value.code == "scheduled_price_exists"
    assert exc.value.detail == "A scheduled price already exists for this model. Delete it first."
    assert AiPricing.objects.filter(model="m").count() == 2
    sched.refresh_from_db()
    assert sched.effective_to is None
    assert not AuditLog.objects.exists()


def test_delete_scheduled_reopens_previous(actor):
    now = timezone.now()
    start = now + timedelta(days=2)
    prev = AiPricingFactory(model="m", effective_from=now - timedelta(days=5), effective_to=start)
    sched = AiPricingFactory(model="m", effective_from=start, effective_to=None)
    sched_pk = sched.pk
    delete_scheduled_price(pricing_id=sched_pk, actor=actor, now=now)
    prev.refresh_from_db()
    assert prev.effective_to is None
    assert AiPricing.objects.get_active(model="m", at=now) == prev
    assert not AiPricing.objects.filter(pk=sched_pk).exists()
    log = AuditLog.objects.get()
    assert (log.action, log.entity_id, log.organisation, log.actor) == (
        "ai_pricing.deleted",
        str(sched_pk),
        None,
        actor,
    )
    assert log.before_data["effective_from"] == start.isoformat()
    assert log.after_data is None


def test_delete_scheduled_without_predecessor(actor):
    now = timezone.now()
    sched = AiPricingFactory(model="m", effective_from=now + timedelta(days=1), effective_to=None)
    delete_scheduled_price(pricing_id=sched.pk, actor=actor, now=now)
    assert not AiPricing.objects.filter(model="m").exists()


def test_delete_current_or_past_price_rejected(actor):
    now = timezone.now()
    past = AiPricingFactory(
        model="m", effective_from=now - timedelta(days=5), effective_to=now - timedelta(days=1)
    )
    cur = AiPricingFactory(model="m", effective_from=now - timedelta(days=1), effective_to=None)
    for row in (past, cur):
        with pytest.raises(PriceNotScheduledError) as exc:
            delete_scheduled_price(pricing_id=row.pk, actor=actor, now=now)
        assert exc.value.code == "price_not_scheduled"
        assert exc.value.detail == "Only a scheduled price that hasn't started yet can be deleted."
    assert AiPricing.objects.filter(model="m").count() == 2
    assert not AuditLog.objects.exists()


def test_delete_unknown_id_raises_does_not_exist(actor):
    with pytest.raises(AiPricing.DoesNotExist):
        delete_scheduled_price(pricing_id=999999, actor=actor)


def test_concurrent_open_row_maps_to_concurrent_change_error(actor):
    now = timezone.now()
    old = AiPricingFactory(model="m", effective_from=now - timedelta(days=5), effective_to=None)
    with (
        mock.patch.object(AiPricing.objects, "create", side_effect=IntegrityError("dup")),
        pytest.raises(ConcurrentPriceChangeError) as exc,
    ):
        _add(actor, now)
    assert exc.value.code == "concurrent_change"
    assert "happened at the same time" in exc.value.detail
    assert AiPricing.objects.filter(model="m").count() == 1
    assert not AuditLog.objects.exists()
    old.refresh_from_db()
    assert old.effective_to is None  # the whole call rolled back, including the close


def test_add_price_invalidates_missing_cache_on_commit(actor, django_capture_on_commit_callbacks):
    cache.set(MISSING_CACHE_KEY, [{"model": "m"}], 600)
    now = timezone.now()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        _add(actor, now)
    assert len(callbacks) == 1
    assert cache.get(MISSING_CACHE_KEY) is None


def test_delete_invalidates_missing_cache_on_commit(actor, django_capture_on_commit_callbacks):
    now = timezone.now()
    sched = AiPricingFactory(model="m", effective_from=now + timedelta(days=1), effective_to=None)
    cache.set(MISSING_CACHE_KEY, [{"model": "m"}], 600)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        delete_scheduled_price(pricing_id=sched.pk, actor=actor, now=now)
    assert len(callbacks) == 1
    assert cache.get(MISSING_CACHE_KEY) is None


def test_never_touches_usage_log(actor):
    now = timezone.now()
    log = AiUsageLogFactory(model="m")
    before = list(AiUsageLog.objects.values())
    _add(actor, now)
    sched = _add(actor, now, offset=timedelta(days=1))
    delete_scheduled_price(pricing_id=sched.pk, actor=actor, now=now)
    assert list(AiUsageLog.objects.values()) == before
    assert log.pk


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(seconds=-1)])
def test_new_price_starting_at_or_before_current_start_rejected(actor, offset):
    """Within the 5 s grace a new price must still start strictly after the open row."""
    now = timezone.now()
    cur = AiPricingFactory(model="m", effective_from=now - timedelta(seconds=2), effective_to=None)
    with pytest.raises(BackdatedPriceError) as exc:
        add_price(
            model="m",
            effective_from=cur.effective_from + offset,
            actor=actor,
            now=now,
            **PRICES,
        )
    assert exc.value.code == "backdated"
    assert "after the current price" in exc.value.detail
    cur.refresh_from_db()
    assert cur.effective_to is None
    assert AiPricing.objects.filter(model="m").count() == 1
    assert not AuditLog.objects.exists()


@pytest.mark.parametrize("source", [AiPricing.Source.SEED, AiPricing.Source.SYNC])
def test_protect_manual_allows_replacing_non_manual_rows(source):
    now = timezone.now()
    AiPricingFactory(model="pm", source=source, effective_from=now - timedelta(days=1))
    new = add_price(
        model="pm",
        input_token_price_per_1m=Decimal(1),
        output_token_price_per_1m=Decimal(1),
        cached_token_price_per_1m=Decimal(0),
        effective_from=now,
        actor=None,
        source=AiPricing.Source.SYNC,
        now=now,
        protect_manual=True,
    )
    assert new.effective_to is None


@pytest.mark.parametrize("protect", [True, False])
def test_protect_manual_refuses_manual_open_row(protect):
    now = timezone.now()
    manual = AiPricingFactory(
        model="pm", source=AiPricing.Source.MANUAL, effective_from=now - timedelta(days=1)
    )
    kwargs = {
        "model": "pm",
        "input_token_price_per_1m": Decimal(1),
        "output_token_price_per_1m": Decimal(1),
        "cached_token_price_per_1m": Decimal(0),
        "effective_from": now,
        "actor": None,
        "source": AiPricing.Source.SYNC,
        "now": now,
        "protect_manual": protect,
    }
    if not protect:  # default: a hand-entered price may replace a manual one
        add_price(**kwargs)
        return
    with pytest.raises(ManualPriceProtectedError) as info:
        add_price(**kwargs)
    assert info.value.code == "manual_price_protected"
    assert info.value.current == manual
    assert list(AiPricing.objects.filter(model="pm")) == [manual]
    manual.refresh_from_db()
    assert manual.effective_to is None
    assert not AuditLog.objects.exists()
