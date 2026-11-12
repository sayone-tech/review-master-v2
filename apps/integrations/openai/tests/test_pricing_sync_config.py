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


def test_overdue_enabled_never_succeeded():
    _configure(enabled=True)
    assert get_sync_status(now=NOW)["overdue"] is True


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
