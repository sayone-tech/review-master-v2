from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.models import AuditLog
from apps.integrations.openai.models import AiPricingSyncConfig
from apps.integrations.openai.selectors.pricing_sync import get_sync_status
from apps.integrations.openai.services.pricing_sync import set_sync_enabled

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)  # a Thursday


@pytest.fixture
def superadmin():
    return UserFactory(role=User.Role.SUPERADMIN)


def test_load_returns_same_single_row():
    first = AiPricingSyncConfig.load()
    second = AiPricingSyncConfig.load()
    assert first.pk == second.pk == 1
    assert AiPricingSyncConfig.objects.count() == 1
    assert first.enabled is False
    assert first.last_status == AiPricingSyncConfig.Status.NEVER


def test_second_row_violates_singleton_constraint():
    AiPricingSyncConfig.load()
    with pytest.raises(IntegrityError), transaction.atomic():
        AiPricingSyncConfig.objects.create(pk=2)


def test_set_sync_enabled_audits_once(superadmin):
    cfg = set_sync_enabled(enabled=True, actor=superadmin)
    assert cfg.enabled is True
    rows = AuditLog.objects.filter(action="ai_pricing.sync_enabled")
    assert rows.count() == 1
    row = rows.get()
    assert row.organisation is None
    assert row.actor == superadmin
    assert row.entity_type == "ai_pricing"
    assert row.entity_id == "sync"
    assert row.before_data == {"enabled": False}
    assert row.after_data == {"enabled": True}

    set_sync_enabled(enabled=True, actor=superadmin)
    assert AuditLog.objects.filter(action__startswith="ai_pricing.sync_").count() == 1

    set_sync_enabled(enabled=False, actor=superadmin)
    assert AuditLog.objects.filter(action="ai_pricing.sync_disabled").count() == 1
    assert AiPricingSyncConfig.load().enabled is False


def _configure(**kw):
    cfg = AiPricingSyncConfig.load()
    for k, v in kw.items():
        setattr(cfg, k, v)
    cfg.save()


def test_overdue_disabled_is_false():
    assert get_sync_status(now=NOW)["overdue"] is False


def _set_updated_at(when):
    AiPricingSyncConfig.objects.filter(pk=1).update(updated_at=when)


def test_fresh_enable_never_run_is_not_overdue():
    _configure(enabled=True)
    _set_updated_at(NOW - timedelta(days=1))
    assert get_sync_status(now=NOW)["overdue"] is False


def test_enabled_never_succeeded_overdue_after_14_days_from_toggle():
    _configure(enabled=True)
    _set_updated_at(NOW - timedelta(days=15))
    assert get_sync_status(now=NOW)["overdue"] is True


def test_enabled_never_succeeded_measures_from_last_run():
    _configure(enabled=True, last_run_at=NOW - timedelta(days=2))
    _set_updated_at(NOW - timedelta(days=30))
    # last_run_at wins over an older toggle time.
    cfg = AiPricingSyncConfig.objects.get(pk=1)
    assert cfg.last_run_at is not None
    assert get_sync_status(now=NOW)["overdue"] is False


@pytest.mark.parametrize(("days", "expected"), [(13, False), (15, True)])
def test_overdue_by_age(days, expected):
    _configure(enabled=True, last_success_at=NOW - timedelta(days=days))
    assert get_sync_status(now=NOW)["overdue"] is expected


def test_next_run_none_when_disabled():
    assert get_sync_status(now=NOW)["next_run_at"] is None


def test_next_run_monday_before_nine():
    _configure(enabled=True)
    monday = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
    assert get_sync_status(now=monday)["next_run_at"] == datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def test_next_run_monday_at_nine_goes_next_week():
    _configure(enabled=True)
    monday = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    assert get_sync_status(now=monday)["next_run_at"] == datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


def test_status_passes_through_fields():
    _configure(last_status="failed", last_error="boom", last_summary={"a": 1})
    s = get_sync_status(now=NOW)
    assert (s["last_status"], s["last_error"], s["summary"]) == ("failed", "boom", {"a": 1})


def test_status_is_read_only_and_never_creates_the_row():
    AiPricingSyncConfig.objects.all().delete()
    s = get_sync_status(now=NOW)
    assert not AiPricingSyncConfig.objects.exists()
    assert (s["enabled"], s["last_status"], s["overdue"], s["summary"]) == (
        False,
        "never",
        False,
        {},
    )


def test_fresh_running_status_passes_through():
    _configure(last_status="running", last_run_at=NOW - timedelta(minutes=14), last_error="old")
    s = get_sync_status(now=NOW)
    assert (s["last_status"], s["last_error"]) == ("running", "old")


@pytest.mark.parametrize("last_run_at", [NOW - timedelta(minutes=16), None])
def test_stale_running_status_reported_as_failed(last_run_at):
    _configure(last_status="running", last_run_at=last_run_at)
    s = get_sync_status(now=NOW)
    assert (s["last_status"], s["last_error"]) == (
        "failed",
        "Sync did not finish (worker stopped).",
    )
    assert AiPricingSyncConfig.load().last_status == "running"  # display only, no write


def test_tolerance_setting_rejects_negative():
    from django.core.exceptions import ImproperlyConfigured

    from config.settings.base import parse_non_negative_decimal

    assert parse_non_negative_decimal("X", "0") == 0
    with pytest.raises(ImproperlyConfigured):
        parse_non_negative_decimal("X", "-0.5")
