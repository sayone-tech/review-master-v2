"""Phase 35 task 1 - AiPricing hardening (source/created_by, one open row, time-aware lookup)."""

from __future__ import annotations

import importlib
from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.admin.sites import site as admin_site
from django.db import IntegrityError, transaction
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.common.models import AuditLog
from apps.integrations.openai.admin import PlatformAuditLogAdmin
from apps.integrations.openai.models import AiPricing, PlatformAuditLog
from apps.integrations.openai.pricing import calculate_cost
from apps.integrations.openai.tests.factories import AiPricingFactory

pytestmark = pytest.mark.django_db


def test_get_active_ignores_scheduled_row():
    now = timezone.now()
    cur = AiPricingFactory(
        model="m", effective_from=now - timedelta(days=10), effective_to=now + timedelta(days=1)
    )
    AiPricingFactory(model="m", effective_from=now + timedelta(days=1), effective_to=None)
    assert AiPricing.objects.get_active(model="m") == cur


def test_get_active_switches_at_scheduled_start():
    now = timezone.now()
    start = now + timedelta(days=1)
    cur = AiPricingFactory(model="m", effective_from=now - timedelta(days=10), effective_to=start)
    nxt = AiPricingFactory(model="m", effective_from=start, effective_to=None)
    assert AiPricing.objects.get_active(model="m", at=start) == nxt
    assert AiPricing.objects.get_active(model="m", at=start - timedelta(microseconds=1)) == cur


def test_get_active_raises_when_no_row_covers_time():
    AiPricingFactory(
        model="m", effective_from=timezone.now() + timedelta(days=1), effective_to=None
    )
    with pytest.raises(AiPricing.DoesNotExist):
        AiPricing.objects.get_active(model="m")


def test_active_at_returns_only_covering_rows():
    now = timezone.now()
    cur = AiPricingFactory(model="a", effective_from=now - timedelta(days=1), effective_to=None)
    AiPricingFactory(model="b", effective_from=now + timedelta(days=1), effective_to=None)
    AiPricingFactory(
        model="c", effective_from=now - timedelta(days=5), effective_to=now - timedelta(days=1)
    )
    assert list(AiPricing.objects.active_at(now).filter(model__in=["a", "b", "c"])) == [cur]


def test_two_open_rows_for_one_model_are_rejected():
    now = timezone.now()
    AiPricingFactory(model="m", effective_from=now - timedelta(days=2), effective_to=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        AiPricingFactory(model="m", effective_from=now - timedelta(days=1), effective_to=None)


def test_source_and_created_by_defaults():
    row = AiPricingFactory(model="m")
    assert row.source == AiPricing.Source.MANUAL
    assert row.created_by is None
    row2 = AiPricingFactory(model="n", source=AiPricing.Source.SYNC, created_by=UserFactory())
    assert row2.created_by_id is not None


def test_backfill_marks_only_the_0002_seed_row_as_seed():
    migration = importlib.import_module(
        "apps.integrations.openai.migrations.0005_ai_pricing_source_created_by"
    )
    seed = AiPricing.objects.get(
        model=migration.SEED_MODEL, effective_from=migration.SEED_EFFECTIVE_FROM
    )
    AiPricing.objects.filter(pk=seed.pk).update(source="sync")  # pre-backfill noise
    admin_row = AiPricingFactory(model="legacy", source="seed")
    same_model_later = AiPricingFactory(
        model=migration.SEED_MODEL,
        effective_from=migration.SEED_EFFECTIVE_FROM + timedelta(days=1),
        effective_to=migration.SEED_EFFECTIVE_FROM + timedelta(days=2),  # one open row/model
        source="seed",
    )
    migration.backfill_source(django_apps, None)
    for row in (seed, admin_row, same_model_later):
        row.refresh_from_db()
    assert seed.source == AiPricing.Source.SEED
    assert admin_row.source == AiPricing.Source.MANUAL
    assert same_model_later.source == AiPricing.Source.MANUAL


def test_0008_marks_hand_entered_seed_rows_manual_and_is_idempotent():
    migration = importlib.import_module(
        "apps.integrations.openai.migrations.0008_backfill_hand_entered_prices_manual"
    )
    seed = AiPricing.objects.get(
        model=migration.SEED_MODEL, effective_from=migration.SEED_EFFECTIVE_FROM
    )
    assert seed.source == AiPricing.Source.SEED
    old_0005_leftover = AiPricingFactory(model="legacy", source="seed")
    same_model_later = AiPricingFactory(
        model=migration.SEED_MODEL,
        effective_from=migration.SEED_EFFECTIVE_FROM + timedelta(days=1),
        effective_to=migration.SEED_EFFECTIVE_FROM + timedelta(days=2),
        source="seed",
    )
    synced = AiPricingFactory(model="synced", source="sync")
    manual = AiPricingFactory(model="hand", source="manual")
    for _ in range(2):  # idempotent
        migration.backfill_hand_entered_manual(django_apps, None)
        rows = {
            r.pk: r.source
            for r in AiPricing.objects.filter(
                pk__in=[seed.pk, old_0005_leftover.pk, same_model_later.pk, synced.pk, manual.pk]
            )
        }
        assert rows == {
            seed.pk: "seed",
            old_0005_leftover.pk: "manual",
            same_model_later.pk: "manual",
            synced.pk: "sync",
            manual.pk: "manual",
        }


def test_0008_seed_identity_matches_0002():
    m0002 = importlib.import_module(
        "apps.integrations.openai.migrations.0002_seed_aiprice_gpt4o_mini"
    )
    m0008 = importlib.import_module(
        "apps.integrations.openai.migrations.0008_backfill_hand_entered_prices_manual"
    )
    assert (m0008.SEED_MODEL, m0008.SEED_EFFECTIVE_FROM) == (
        m0002.GPT4O_MINI_MODEL,
        m0002.EFFECTIVE_FROM,
    )


def test_calculate_cost_unchanged_with_scheduled_row():
    now = timezone.now()
    AiPricingFactory(
        model="m",
        effective_from=now - timedelta(days=10),
        effective_to=now + timedelta(days=1),
        input_token_price_per_1m=Decimal("1"),
        output_token_price_per_1m=Decimal("2"),
        cached_token_price_per_1m=Decimal("0.5"),
    )
    AiPricingFactory(
        model="m",
        effective_from=now + timedelta(days=1),
        effective_to=None,
        input_token_price_per_1m=Decimal("100"),
        output_token_price_per_1m=Decimal("100"),
        cached_token_price_per_1m=Decimal("100"),
    )
    cost = calculate_cost(model="m", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == Decimal("3.000000")


def test_pricing_admin_is_read_only(rf: RequestFactory):
    request = rf.get("/")
    request.user = UserFactory(is_superuser=True, is_staff=True)
    ma = admin_site._registry[AiPricing]
    obj = AiPricingFactory(model="m")
    assert not ma.has_add_permission(request)
    assert not ma.has_change_permission(request, obj)
    assert not ma.has_delete_permission(request, obj)


def test_platform_audit_admin_filters_and_is_read_only():
    AuditLog.objects.create(
        organisation=None, entity_type="ai_pricing", entity_id="1", action="ai_pricing.added"
    )
    AuditLog.objects.create(organisation=None, entity_type="other", entity_id="1", action="x")
    request = RequestFactory().get("/")
    request.user = UserFactory(is_superuser=True, is_staff=True)
    ma = admin_site._registry[PlatformAuditLog]
    assert isinstance(ma, PlatformAuditLogAdmin)
    assert [r.action for r in ma.get_queryset(request)] == ["ai_pricing.added"]
    assert not ma.has_add_permission(request)
    assert not ma.has_change_permission(request)
    assert not ma.has_delete_permission(request)


def test_get_active_overlapping_windows_newest_start_wins():
    """Overlapping windows (hand edit / grace edge) must not raise MultipleObjectsReturned."""
    now = timezone.now()
    AiPricingFactory(
        model="m", effective_from=now - timedelta(days=10), effective_to=now + timedelta(days=1)
    )
    newer = AiPricingFactory(model="m", effective_from=now - timedelta(days=2), effective_to=None)
    assert AiPricing.objects.get_active(model="m") == newer
    cost = calculate_cost(model="m", prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == newer.input_token_price_per_1m.quantize(Decimal("0.000001"))
