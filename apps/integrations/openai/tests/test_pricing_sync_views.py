"""Phase 36 Task 5: sync status / toggle / trigger APIs."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.common.models import AuditLog
from apps.common.throttling import SyncTriggerThrottle
from apps.integrations.openai.models import AiPricingSyncConfig
from apps.integrations.openai.services.pricing_sync import SyncOutcome, SyncSummary

STATUS_URL = reverse("superadmin-ai-pricing-sync-status")
TOGGLE_URL = reverse("superadmin-ai-pricing-sync-toggle")
TRIGGER_URL = reverse("superadmin-ai-pricing-sync-trigger")
TASK = "apps.integrations.openai.pricing_views.sync_ai_pricing_from_litellm_task"
EMPTY_SUMMARY = {
    "added": [],
    "updated": [],
    "unchanged": [],
    "skipped_manual": [],
    "skipped_scheduled": [],
    "skipped_concurrent": [],
    "unpriced": [],
    "errored": [],
}


@pytest.fixture(autouse=True)
def delay_mock():
    """Never enqueue for real, whatever a test does with on_commit."""
    with patch(f"{TASK}.delay") as delay:
        yield delay


def _post(client, url, body=None):
    return client.post(url, body or {}, format="json")


@pytest.mark.parametrize(
    ("method", "url"),
    [("get", STATUS_URL), ("post", TOGGLE_URL), ("post", TRIGGER_URL)],
)
def test_non_superadmin_forbidden(db, method, url):
    for user in (OrgAdminFactory(), StaffAdminFactory()):
        client = APIClient()
        client.force_authenticate(user)
        assert getattr(client, method)(url, {"enabled": True}, format="json").status_code == 403
    assert getattr(APIClient(), method)(url).status_code in (401, 403)


def test_csrf_enforced_on_toggle_and_trigger(db):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(UserFactory(role=User.Role.SUPERADMIN))
    assert _post(client, TOGGLE_URL, {"enabled": True}).status_code == 403
    assert _post(client, TRIGGER_URL).status_code == 403
    assert AiPricingSyncConfig.load().enabled is False


def test_status_never_run(superadmin_client):
    resp = superadmin_client.get(STATUS_URL)
    assert resp.status_code == 200
    assert resp.json() == {
        "enabled": False,
        "last_run_at": None,
        "last_success_at": None,
        "last_status": "never",
        "last_error": "",
        "overdue": False,
        "next_run_at": None,
        "summary": EMPTY_SUMMARY,
    }


def test_status_after_completed_run(superadmin_client):
    summary = SyncSummary(outcome=SyncOutcome.COMPLETED)
    summary.added = ["m1"]
    summary.unpriced = ["cfg"]
    stored = summary.as_json()
    stored["skipped_manual"] = [
        {
            "model": "m3",
            "ours": {"input": "0.15000000", "output": "0.60000000", "cached": "0.07500000"},
            "litellm": {"input": "0.10000000", "output": "0.40000000", "cached": "0.05000000"},
        }
    ]
    now = timezone.now()
    config = AiPricingSyncConfig.load()
    AiPricingSyncConfig.objects.filter(pk=config.pk).update(
        enabled=True,
        last_run_at=now,
        last_success_at=now,
        last_status="success",
        last_summary=stored,
    )
    body = superadmin_client.get(STATUS_URL).json()
    assert body["enabled"] is True
    assert body["last_status"] == "success"
    assert body["overdue"] is False
    assert body["next_run_at"] is not None
    assert body["summary"]["added"] == ["m1"]
    assert body["summary"]["unpriced"] == ["cfg"]
    assert body["summary"]["skipped_manual"] == stored["skipped_manual"]
    assert set(body["summary"]) == set(EMPTY_SUMMARY)


def test_status_after_failure_is_overdue(superadmin_client):
    config = AiPricingSyncConfig.load()
    AiPricingSyncConfig.objects.filter(pk=config.pk).update(
        enabled=True,
        last_run_at=timezone.now() - timedelta(days=15),
        last_status="failed",
        last_error="fetch failed: timeout",
    )
    body = superadmin_client.get(STATUS_URL).json()
    assert body["last_status"] == "failed"
    assert body["last_error"] == "fetch failed: timeout"
    assert body["overdue"] is True
    assert body["summary"] == EMPTY_SUMMARY


def test_toggle_on_off_returns_state_and_audits(superadmin_client):
    on = _post(superadmin_client, TOGGLE_URL, {"enabled": True})
    assert on.status_code == 200
    assert on.json()["enabled"] is True
    assert on.json()["next_run_at"] is not None
    off = _post(superadmin_client, TOGGLE_URL, {"enabled": False})
    assert off.json()["enabled"] is False
    actions = list(
        AuditLog.objects.filter(entity_type="ai_pricing", entity_id="sync")
        .order_by("id")
        .values_list("action", flat=True)
    )
    assert actions == ["ai_pricing.sync_enabled", "ai_pricing.sync_disabled"]


@pytest.mark.parametrize("body", [{}, {"enabled": "maybe"}, {"enabled": None}, {"enabled": [1]}])
def test_toggle_rejects_bad_body(superadmin_client, body):
    resp = _post(superadmin_client, TOGGLE_URL, body)
    assert resp.status_code == 400
    assert "enabled" in resp.json()
    assert AiPricingSyncConfig.load().enabled is False


def test_trigger_enqueues_once_on_commit(
    superadmin_client, django_capture_on_commit_callbacks, delay_mock
):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        resp = _post(superadmin_client, TRIGGER_URL)
    assert resp.status_code == 202
    assert resp.json() == {"queued": True}
    assert len(callbacks) == 1
    delay_mock.assert_called_once_with(force=True)


def test_trigger_works_while_disabled(superadmin_client):
    assert AiPricingSyncConfig.load().enabled is False
    assert _post(superadmin_client, TRIGGER_URL).status_code == 202


def test_trigger_throttled_per_user_for_15_minutes(db):
    user = UserFactory(role=User.Role.SUPERADMIN)
    other = UserFactory(role=User.Role.SUPERADMIN)
    client, other_client = APIClient(), APIClient()
    client.force_authenticate(user)
    other_client.force_authenticate(other)
    t0 = 1_000_000.0
    with patch.object(SyncTriggerThrottle, "timer", return_value=t0):
        assert _post(client, TRIGGER_URL).status_code == 202
        second = _post(client, TRIGGER_URL)
        assert second.status_code == 429
        assert "detail" in second.json()
        assert _post(other_client, TRIGGER_URL).status_code == 202
    with patch.object(SyncTriggerThrottle, "timer", return_value=t0 + 899):
        assert _post(client, TRIGGER_URL).status_code == 429
    with patch.object(SyncTriggerThrottle, "timer", return_value=t0 + 901):
        assert _post(client, TRIGGER_URL).status_code == 202


def test_trigger_rate_setting_and_parse_rate(settings):
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][SyncTriggerThrottle.scope] == "1/15m"
    throttle = SyncTriggerThrottle()
    assert throttle.parse_rate("1/15m") == (1, 900)
    assert throttle.parse_rate("10/m") == (10, 60)
    assert throttle.parse_rate("1/2h") == (1, 7200)
    assert throttle.parse_rate("5/day") == (5, 86400)


@pytest.mark.parametrize("bad", ["1/15x", "1/", "abc/m", "1-15m"])
def test_parse_rate_malformed_raises_improperly_configured(bad):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        SyncTriggerThrottle().parse_rate(bad)


def test_status_passes_fresh_running_through(superadmin_client):
    config = AiPricingSyncConfig.load()
    AiPricingSyncConfig.objects.filter(pk=config.pk).update(
        last_run_at=timezone.now(), last_status="running"
    )
    body = superadmin_client.get(STATUS_URL).json()
    assert body["last_status"] == "running"
    assert body["last_error"] == ""


def test_query_ceilings(superadmin_client):
    with CaptureQueriesContext(connection) as ctx:
        assert superadmin_client.get(STATUS_URL).status_code == 200
    assert len(ctx.captured_queries) <= 3
    with CaptureQueriesContext(connection) as ctx:
        assert _post(superadmin_client, TOGGLE_URL, {"enabled": True}).status_code == 200
    real = [q for q in ctx.captured_queries if "SAVEPOINT" not in q["sql"]]
    assert len(real) <= 6
