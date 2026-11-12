"""LiteLLM pricing sync service (Phase 36, Task 3). Never hits the network or Redis."""

from __future__ import annotations

import contextlib
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import httpx
import pytest
from django.utils import timezone

from apps.common.models import AuditLog
from apps.integrations.openai.models import AiPricing, AiPricingSyncConfig, AiUsageLog
from apps.integrations.openai.services import pricing_management, pricing_sync
from apps.integrations.openai.services.pricing_management import add_price
from apps.integrations.openai.services.pricing_sync import (
    SyncOutcome,
    run_pricing_sync,
)
from apps.integrations.openai.tests.factories import AiPricingFactory, AiUsageLogFactory

pytestmark = pytest.mark.django_db

CFG_MODEL = "cfg-model"
SEED = AiPricing.Source.SEED
SYNC = AiPricing.Source.SYNC
MANUAL = AiPricing.Source.MANUAL


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.OPENAI_MODEL = CFG_MODEL
    settings.AI_PRICING_SYNC_TOLERANCE_USD_PER_1M = Decimal("0.000001")


@pytest.fixture(autouse=True)
def lock_acquired():
    """No Redis in tests: the lock is always acquired unless a test overrides it."""

    @contextlib.contextmanager
    def fake_lock(key, timeout=300, blocking=False):
        assert key == "lock:ai_pricing:sync"
        yield True

    with mock.patch.object(pricing_sync, "distributed_lock", side_effect=fake_lock) as m:
        yield m


@pytest.fixture
def now():
    return timezone.now()


def _entry(inp, out, cached=None):
    e = {"input_cost_per_token": inp, "output_cost_per_token": out}
    if cached is not None:
        e["cache_read_input_token_cost"] = cached
    return e


def _transport(payload, calls=None, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


# 0.15 / 0.60 / 0.075 per 1M — matches AiPricingFactory defaults.
SAME = _entry(1.5e-7, 6e-7, 7.5e-8)
CHEAPER = _entry(1e-7, 4e-7, 5e-8)


def _enable():
    cfg = AiPricingSyncConfig.load()
    cfg.enabled = True
    cfg.save()


def _use(*models):
    for m in models:
        AiUsageLogFactory(model=m)


def _rows():
    return set(AiPricing.objects.values_list("pk", "effective_to"))


def _open_row(model):
    return AiPricing.objects.get(model=model, effective_to__isnull=True)


def test_disabled_scheduled_run_does_nothing(now):
    _use("m1")
    baseline = _rows()
    calls: list[httpx.Request] = []
    summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}, calls))
    assert summary.outcome is SyncOutcome.SKIPPED_DISABLED
    assert calls == []
    assert _rows() == baseline
    assert not AuditLog.objects.exists()
    cfg = AiPricingSyncConfig.load()
    assert (cfg.last_run_at, cfg.last_status) == (None, AiPricingSyncConfig.Status.NEVER)


def test_force_runs_even_when_disabled(now):
    _use("m1")
    summary = run_pricing_sync(force=True, now=now, transport=_transport({"m1": SAME}))
    assert summary.outcome is SyncOutcome.COMPLETED
    assert summary.added == ["m1"]
    cfg = AiPricingSyncConfig.load()
    assert cfg.enabled is False  # force never flips the switch
    assert cfg.last_status == AiPricingSyncConfig.Status.SUCCESS


def test_case_a_adds_price_for_unpriced_used_model(now):
    _enable()
    _use("m1")
    summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.added == ["m1"]
    row = _open_row("m1")
    assert row.source == SYNC
    assert row.effective_from == now
    assert row.created_by is None
    assert (
        row.input_token_price_per_1m,
        row.output_token_price_per_1m,
        row.cached_token_price_per_1m,
    ) == (Decimal("0.15"), Decimal("0.6"), Decimal("0.075"))
    audit = AuditLog.objects.get(action="ai_pricing.added_from_sync")
    assert audit.entity_id == str(row.pk)
    assert audit.actor is None
    assert audit.organisation is None
    assert not AuditLog.objects.filter(action="ai_pricing.added").exists()


def test_case_b_within_tolerance_unchanged(now):
    _enable()
    _use("m1")
    AiPricingFactory(
        model="m1",
        source=SEED,
        input_token_price_per_1m=Decimal("0.15000050"),  # 5e-7 off: inside 1e-6
    )
    summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.unchanged == ["m1"]
    assert summary.added == summary.updated == []
    assert AiPricing.objects.filter(model="m1").count() == 1


def test_case_b_tolerance_checks_cached_field_too(now):
    _enable()
    _use("m1")
    AiPricingFactory(model="m1", source=SEED, cached_token_price_per_1m=Decimal("0.07"))
    summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.updated == ["m1"]


@pytest.mark.parametrize("source", [SEED, SYNC])
def test_case_c_updates_sync_or_seed_price(now, source):
    _enable()
    _use("m1")
    old = AiPricingFactory(model="m1", source=source)
    summary = run_pricing_sync(now=now, transport=_transport({"m1": CHEAPER}))
    assert summary.updated == ["m1"]
    old.refresh_from_db()
    assert old.effective_to == now
    new = _open_row("m1")
    assert (new.source, new.effective_from) == (SYNC, now)
    assert new.input_token_price_per_1m == Decimal("0.1")
    audit = AuditLog.objects.get(action="ai_pricing.updated_from_sync")
    assert audit.entity_id == str(new.pk)
    assert audit.before_data["source"] == source


def test_manual_price_never_overridden(now):
    _enable()
    _use("m1")
    manual = AiPricingFactory(model="m1", source=MANUAL)
    for _ in range(2):
        summary = run_pricing_sync(now=now, transport=_transport({"m1": CHEAPER}))
        assert summary.skipped_manual == [
            {
                "model": "m1",
                "ours": {
                    "input": Decimal("0.15"),
                    "output": Decimal("0.6"),
                    "cached": Decimal("0.075"),
                },
                "litellm": {
                    "input": Decimal("0.1"),
                    "output": Decimal("0.4"),
                    "cached": Decimal("0.05"),
                },
            }
        ]
        assert summary.added == summary.updated == []
    assert list(AiPricing.objects.filter(model="m1")) == [manual]
    manual.refresh_from_db()
    assert manual.effective_to is None
    assert summary.as_json()["skipped_manual"] == [
        {
            "model": "m1",
            "ours": {"input": "0.15000000", "output": "0.60000000", "cached": "0.07500000"},
            "litellm": {"input": "0.10000000", "output": "0.40000000", "cached": "0.05000000"},
        }
    ]


def test_scheduled_price_pending_is_skipped_not_fatal(now):
    _enable()
    _use("m1", "m2")
    current = AiPricingFactory(model="m1", source=SEED, effective_to=now + timedelta(days=3))
    AiPricingFactory(
        model="m1", source=MANUAL, effective_from=now + timedelta(days=3), effective_to=None
    )
    summary = run_pricing_sync(now=now, transport=_transport({"m1": CHEAPER, "m2": SAME}))
    assert summary.skipped_scheduled == ["m1"]
    assert summary.added == ["m2"]
    assert summary.outcome is SyncOutcome.COMPLETED
    assert AiPricing.objects.filter(model="m1").count() == 2
    current.refresh_from_db()
    assert current.effective_to == now + timedelta(days=3)


def test_scheduled_error_raised_by_add_price_is_skipped(now):
    """Race: the scheduled row appears between the pre-check and add_price."""
    _enable()
    _use("m1")
    from apps.integrations.openai.services.pricing_management import ScheduledPriceExistsError

    with mock.patch.object(pricing_sync, "add_price", side_effect=ScheduledPriceExistsError):
        summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.skipped_scheduled == ["m1"]
    assert summary.errored == []


def test_model_not_in_litellm_is_unpriced(now):
    _enable()
    _use("m1")
    summary = run_pricing_sync(now=now, transport=_transport({"other": SAME}))
    assert "m1" in summary.unpriced
    assert not AiPricing.objects.filter(model="m1").exists()


def test_unusable_entry_is_unpriced(now):
    _enable()
    _use("m1")
    summary = run_pricing_sync(
        now=now, transport=_transport({"m1": {"input_cost_per_token": 1e-7}})
    )
    assert "m1" in summary.unpriced
    assert not AiPricing.objects.filter(model="m1").exists()


@pytest.mark.parametrize(
    "entry",
    [
        _entry(2e-3, 1e-7),  # 2000 per 1M — above the 1000 API cap
        _entry(1e-7, 1e-7, 5e-3),  # cached overflow
        _entry(1e-7, 1e-1),  # 100000 per 1M — beyond numeric(12,8)
    ],
)
def test_out_of_range_price_is_unpriced_not_fatal(now, entry):
    _enable()
    _use("m1", "m2")
    summary = run_pricing_sync(now=now, transport=_transport({"m1": entry, "m2": SAME}))
    assert summary.outcome is SyncOutcome.COMPLETED
    assert "m1" in summary.unpriced
    assert summary.added == ["m2"]
    assert summary.errored == []
    assert not AiPricing.objects.filter(model="m1").exists()


def test_configured_model_included_without_usage(now):
    _enable()
    summary = run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    assert summary.added == [CFG_MODEL]


def test_models_not_used_are_never_added(now):
    _enable()
    _use("m1")
    old = AiUsageLogFactory(model="old-model")
    AiUsageLog.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=91))
    run_pricing_sync(
        now=now,
        transport=_transport({"m1": SAME, "unused": SAME, "old-model": SAME, CFG_MODEL: SAME}),
    )
    added = AiPricing.objects.filter(source=SYNC).values_list("model", flat=True)
    assert set(added) == {"m1", CFG_MODEL}


def test_newly_used_model_is_picked_up_despite_usage_cache(now):
    _enable()
    from apps.integrations.openai.selectors.pricing import list_missing_pricing_models

    list_missing_pricing_models(now=now)  # warms the recent-usage cache without m1
    _use("m1")
    summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.added == ["m1"]


def test_fetch_failure_changes_nothing_and_records_error(now, caplog):
    _enable()
    _use("m1")
    seed = AiPricingFactory(model="m1", source=SEED)
    baseline = _rows()
    with caplog.at_level("WARNING"):
        summary = run_pricing_sync(now=now, transport=_transport({}, status=503))
    assert summary.outcome is SyncOutcome.FAILED
    assert summary.error == "LiteLLM returned HTTP 503"
    assert _rows() == baseline
    assert (seed.pk, None) in baseline
    cfg = AiPricingSyncConfig.load()
    assert cfg.last_status == AiPricingSyncConfig.Status.FAILED
    assert cfg.last_error == "LiteLLM returned HTTP 503"
    assert cfg.last_run_at == now
    assert cfg.last_success_at is None
    assert cfg.enabled is True
    audit = AuditLog.objects.get(action="ai_pricing.sync_failed")
    assert (audit.entity_type, audit.entity_id, audit.actor, audit.organisation) == (
        "ai_pricing",
        "sync",
        None,
        None,
    )
    assert audit.after_data == {"error": "LiteLLM returned HTTP 503"}
    assert "LiteLLM returned HTTP 503" in caplog.text


def test_concurrent_run_skipped_when_locked(now, lock_acquired):
    _enable()
    _use("m1")

    @contextlib.contextmanager
    def held(key, timeout=300, blocking=False):
        yield False

    lock_acquired.side_effect = held
    baseline = _rows()
    calls: list[httpx.Request] = []
    summary = run_pricing_sync(force=True, now=now, transport=_transport({"m1": SAME}, calls))
    assert summary.outcome is SyncOutcome.SKIPPED_LOCKED
    assert calls == []
    assert _rows() == baseline
    assert AiPricingSyncConfig.load().last_run_at is None


def test_second_run_is_idempotent(now):
    _enable()
    _use("m1", "m2")
    payload = {"m1": SAME, "m2": CHEAPER, CFG_MODEL: SAME}
    first = run_pricing_sync(now=now, transport=_transport(payload))
    assert sorted(first.added) == sorted(["m1", "m2", CFG_MODEL])
    rows = AiPricing.objects.count()
    second = run_pricing_sync(now=now + timedelta(hours=1), transport=_transport(payload))
    assert second.added == second.updated == []
    assert second.unchanged == sorted(["m1", "m2", CFG_MODEL])
    assert AiPricing.objects.count() == rows


def test_completed_run_records_summary_and_audit(now, django_capture_on_commit_callbacks):
    _enable()
    _use("m1", "m2", "m3")
    AiPricingFactory(model="m2", source=SEED)
    AiPricingFactory(model="m3", source=MANUAL)
    with django_capture_on_commit_callbacks(execute=True):
        summary = run_pricing_sync(
            now=now, transport=_transport({"m1": SAME, "m2": CHEAPER, "m3": CHEAPER})
        )
    data = summary.as_json()
    assert data == {
        "outcome": "completed",
        "added": ["m1"],
        "updated": ["m2"],
        "unchanged": [],
        "skipped_manual": [
            {
                "model": "m3",
                "ours": {"input": "0.15000000", "output": "0.60000000", "cached": "0.07500000"},
                "litellm": {"input": "0.10000000", "output": "0.40000000", "cached": "0.05000000"},
            }
        ],
        "skipped_scheduled": [],
        "skipped_concurrent": [],
        "unpriced": [CFG_MODEL],
        "errored": [],
        "error": "",
    }
    cfg = AiPricingSyncConfig.load()
    assert cfg.last_status == AiPricingSyncConfig.Status.SUCCESS
    assert (cfg.last_run_at, cfg.last_success_at) == (now, now)
    assert cfg.last_error == ""
    assert cfg.last_summary == data
    audit = AuditLog.objects.get(action="ai_pricing.sync_completed")
    assert (audit.entity_id, audit.actor, audit.organisation) == ("sync", None, None)
    assert audit.after_data == {
        "counts": {
            "added": 1,
            "updated": 1,
            "unchanged": 0,
            "skipped_manual": 1,
            "skipped_scheduled": 0,
            "skipped_concurrent": 0,
            "unpriced": 1,
            "errored": 0,
        },
        "skipped_manual": data["skipped_manual"],
        "unpriced": [CFG_MODEL],
    }


def test_success_clears_previous_error_and_keeps_enabled(now):
    _enable()
    run_pricing_sync(now=now, transport=_transport({}, status=500))
    run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    cfg = AiPricingSyncConfig.load()
    assert (cfg.last_status, cfg.last_error, cfg.enabled) == ("success", "", True)


def test_price_change_invalidates_missing_cache(now, django_capture_on_commit_callbacks):
    _enable()
    with (
        mock.patch.object(pricing_management, "invalidate_missing_pricing_cache") as inv,
        django_capture_on_commit_callbacks(execute=True),
    ):
        run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    inv.assert_called_once_with()


def test_no_change_does_not_invalidate_cache(now, django_capture_on_commit_callbacks):
    _enable()
    with (
        mock.patch.object(pricing_management, "invalidate_missing_pricing_cache") as inv,
        django_capture_on_commit_callbacks(execute=True),
    ):
        run_pricing_sync(now=now, transport=_transport({}))
    inv.assert_not_called()


def test_per_model_error_isolated(now):
    _enable()
    _use("m1", "m2")

    def flaky(**kw):
        if kw["model"] == "m1":
            raise RuntimeError("boom")
        return add_price(**kw)

    with mock.patch.object(pricing_sync, "add_price", side_effect=flaky):
        summary = run_pricing_sync(
            now=now, transport=_transport({"m1": SAME, "m2": SAME, CFG_MODEL: SAME})
        )
    assert summary.outcome is SyncOutcome.COMPLETED
    assert summary.errored == ["m1"]
    assert sorted(summary.added) == sorted(["m2", CFG_MODEL])
    assert not AiPricing.objects.filter(model="m1").exists()


def test_never_touches_usage_log(now):
    _enable()
    log = AiUsageLogFactory(model="m1")
    before = AiUsageLog.objects.values().get(pk=log.pk)
    run_pricing_sync(now=now, transport=_transport({"m1": CHEAPER}))
    assert AiUsageLog.objects.count() == 1
    assert AiUsageLog.objects.values().get(pk=log.pk) == before


def test_add_price_default_audit_action_unchanged(now):
    add_price(
        model="x",
        input_token_price_per_1m=Decimal(1),
        output_token_price_per_1m=Decimal(1),
        cached_token_price_per_1m=Decimal(0),
        effective_from=now,
        actor=None,
        now=now,
    )
    assert AuditLog.objects.filter(action="ai_pricing.added").count() == 1


def _assert_crash_recorded(summary, error):
    assert summary.outcome is SyncOutcome.FAILED
    assert summary.error == error
    cfg = AiPricingSyncConfig.load()
    assert (cfg.last_status, cfg.last_error, cfg.enabled) == ("failed", error, True)
    audit = AuditLog.objects.get(action="ai_pricing.sync_failed")
    assert (audit.entity_id, audit.actor, audit.organisation) == ("sync", None, None)
    assert audit.after_data == {"error": error}


def test_crash_outside_model_loop_recorded_as_failed_and_lock_released(now, lock_acquired):
    _enable()
    released: list[bool] = []

    @contextlib.contextmanager
    def tracking_lock(key, timeout=300, blocking=False):
        try:
            yield True
        finally:
            released.append(True)

    lock_acquired.side_effect = tracking_lock
    with mock.patch.object(
        pricing_sync, "list_recent_usage_models", side_effect=RuntimeError("secret detail")
    ):
        summary = run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    _assert_crash_recorded(summary, "Sync failed unexpectedly (RuntimeError)")
    assert "secret detail" not in AiPricingSyncConfig.load().last_error
    assert released == [True]
    assert AiPricingSyncConfig.load().last_success_at is None


def test_crash_in_success_audit_recorded_as_failed(now):
    _enable()
    original = pricing_sync._sync_audit

    def failing(action, after_data):
        if action == "ai_pricing.sync_completed":
            raise ValueError("audit write failed")
        original(action, after_data)

    with mock.patch.object(pricing_sync, "_sync_audit", side_effect=failing):
        summary = run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    _assert_crash_recorded(summary, "Sync failed unexpectedly (ValueError)")
    cfg = AiPricingSyncConfig.load()
    assert cfg.last_success_at is None
    assert cfg.last_summary == {}


# --- Task 7 audit fixes ---------------------------------------------------------------------


def test_manual_price_landing_mid_sync_is_protected_under_the_row_lock(now):
    """Race (ORM I1): the unlocked check sees a seed row; an admin's manual price replaces it
    before add_price locks the open row. add_price must refuse, and the run reports it."""
    _enable()
    _use("m1")
    AiPricingFactory(model="m1", source=SEED, effective_from=now - timedelta(days=2))
    real_add_price = pricing_sync.add_price

    def admin_wins_the_race(**kw):
        manual = add_price(
            model="m1",
            input_token_price_per_1m=Decimal("0.2"),
            output_token_price_per_1m=Decimal("0.8"),
            cached_token_price_per_1m=Decimal("0.1"),
            effective_from=now - timedelta(days=1),
            actor=None,
            now=now - timedelta(days=1),
        )
        assert manual.source == MANUAL
        return real_add_price(**kw)

    with mock.patch.object(pricing_sync, "add_price", side_effect=admin_wins_the_race):
        summary = run_pricing_sync(now=now, transport=_transport({"m1": CHEAPER}))
    assert summary.updated == summary.added == summary.errored == []
    assert summary.skipped_manual == [
        {
            "model": "m1",
            "ours": {"input": Decimal("0.2"), "output": Decimal("0.8"), "cached": Decimal("0.1")},
            "litellm": {
                "input": Decimal("0.1"),
                "output": Decimal("0.4"),
                "cached": Decimal("0.05"),
            },
        }
    ]
    assert _open_row("m1").source == MANUAL
    assert not AiPricing.objects.filter(model="m1", source=SYNC).exists()


def test_concurrent_price_change_is_skipped_concurrent(now):
    _enable()
    _use("m1")
    from apps.integrations.openai.services.pricing_management import ConcurrentPriceChangeError

    with mock.patch.object(pricing_sync, "add_price", side_effect=ConcurrentPriceChangeError):
        summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert summary.skipped_concurrent == ["m1"]
    assert summary.errored == []
    assert summary.counts()["skipped_concurrent"] == 1
    assert AiPricingSyncConfig.load().last_summary["skipped_concurrent"] == ["m1"]


def test_soft_time_limit_is_reraised_out_of_the_model_loop(now):
    from celery.exceptions import SoftTimeLimitExceeded

    _use("m1")
    with (
        mock.patch.object(pricing_sync, "_sync_model", side_effect=SoftTimeLimitExceeded()),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        pricing_sync._run_locked(now=now, fixed_now=True, transport=_transport({"m1": SAME}))


def test_soft_time_limit_stops_the_run_and_is_recorded_as_failed(now):
    from celery.exceptions import SoftTimeLimitExceeded

    _enable()
    _use("m1", "m2")
    seen: list[str] = []

    def out_of_time(**kw):
        seen.append(kw["model"])
        raise SoftTimeLimitExceeded()

    with mock.patch.object(pricing_sync, "_sync_model", side_effect=out_of_time):
        summary = run_pricing_sync(now=now, transport=_transport({"m1": SAME}))
    assert seen == [CFG_MODEL]  # first model in sorted order; the rest never ran
    _assert_crash_recorded(summary, "Sync failed unexpectedly (SoftTimeLimitExceeded)")


def test_run_marks_running_at_start(now):
    _enable()
    seen = {}

    def handler(request):
        cfg = AiPricingSyncConfig.load()
        seen["state"] = (cfg.last_status, cfg.last_run_at)
        return httpx.Response(200, json={})

    run_pricing_sync(now=now, transport=httpx.MockTransport(handler))
    assert seen["state"] == ("running", now)
    assert AiPricingSyncConfig.load().last_status == "success"


def test_each_new_price_starts_when_it_is_written(lock_acquired):
    """ORM minor 5: without an injected ``now`` each model's row starts at its own write time."""
    _enable()
    _use("m1", "m2")
    start = timezone.now()
    ticks = iter(start + timedelta(seconds=i) for i in range(100))
    with mock.patch.object(pricing_sync.timezone, "now", side_effect=lambda: next(ticks)):
        summary = run_pricing_sync(transport=_transport({"m1": SAME, "m2": SAME}))
    assert sorted(summary.added) == ["m1", "m2"]
    run_start = AiPricingSyncConfig.load().last_run_at
    assert run_start == start
    starts = {_open_row(m).effective_from for m in ("m1", "m2")}
    assert len(starts) == 2
    assert all(s > run_start for s in starts)


def test_lock_error_recorded_as_failed_not_skipped(now, lock_acquired):
    import redis

    _enable()
    lock_acquired.side_effect = redis.exceptions.ConnectionError("redis down: secret-host")
    baseline = _rows()
    summary = run_pricing_sync(now=now, transport=_transport({CFG_MODEL: SAME}))
    _assert_crash_recorded(summary, "Could not acquire sync lock (ConnectionError).")
    assert "secret-host" not in summary.error
    assert _rows() == baseline
