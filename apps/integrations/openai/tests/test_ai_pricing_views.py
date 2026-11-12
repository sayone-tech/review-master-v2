from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.accounts.tests.factories import OrgAdminFactory, StaffAdminFactory, UserFactory
from apps.integrations.openai.models import AiPricing
from apps.integrations.openai.tests.factories import AiPricingFactory, AiUsageLogFactory

LIST_URL = reverse("superadmin-ai-pricing-list")
HISTORY_URL = reverse("superadmin-ai-pricing-history")
SUGGEST_URL = reverse("superadmin-ai-pricing-suggestions")
MISSING_URL = reverse("superadmin-ai-pricing-missing")
REFRESH_URL = reverse("superadmin-ai-pricing-missing-refresh")
ALL_GET_URLS = [LIST_URL, f"{HISTORY_URL}?model=m", SUGGEST_URL, MISSING_URL]

PAST = datetime(2025, 1, 1, tzinfo=UTC)
ROW_KEYS = {
    "id",
    "model",
    "input_token_price_per_1m",
    "output_token_price_per_1m",
    "cached_token_price_per_1m",
    "effective_from",
    "effective_to",
    "source",
    "created_by",
    "status",
    "can_delete",
}


@pytest.fixture(autouse=True)
def _no_seeded_prices(db):
    """Migration 0002 seeds a gpt-4o-mini price; start each test from an empty table."""
    AiPricing.objects.all().delete()


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
@pytest.mark.parametrize("url", ALL_GET_URLS)
def test_non_superadmin_gets_403(db, factory, url):
    c = APIClient()
    c.force_authenticate(factory())
    assert c.get(url).status_code == 403


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_non_superadmin_cannot_refresh(db, factory):
    c = APIClient()
    c.force_authenticate(factory())
    assert c.post(REFRESH_URL).status_code == 403


@pytest.mark.parametrize("url", ALL_GET_URLS)
def test_anonymous_refused(db, url):
    assert APIClient().get(url).status_code in (401, 403)


def test_anonymous_cannot_refresh(db):
    assert APIClient().post(REFRESH_URL).status_code in (401, 403)


def _scheduled_pair(model="gpt-x"):
    """A closed past row, the current row, and a scheduled row for one model."""
    now = timezone.now()
    past = AiPricingFactory(model=model, effective_from=PAST, effective_to=now - timedelta(days=10))
    current = AiPricingFactory(
        model=model,
        effective_from=now - timedelta(days=10),
        effective_to=now + timedelta(days=5),
        source=AiPricing.Source.SEED,
    )
    scheduled = AiPricingFactory(
        model=model,
        effective_from=now + timedelta(days=5),
        effective_to=None,
        input_token_price_per_1m=Decimal("1.5"),
    )
    return past, current, scheduled


def test_list_shape_and_values(superadmin_client):
    user = UserFactory(full_name="Ada Admin")
    _, current, scheduled = _scheduled_pair("gpt-x")
    AiPricingFactory(model="a-model", created_by=user)
    body = superadmin_client.get(LIST_URL).json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 2
    assert [r["model"] for r in body["results"]] == ["a-model", "gpt-x"]
    first, second = body["results"]
    assert set(first) == {"model", "current", "scheduled"}
    assert first["scheduled"] is None
    assert set(first["current"]) == ROW_KEYS
    assert first["current"]["created_by"] == {"id": user.pk, "name": "Ada Admin"}
    assert first["current"]["input_token_price_per_1m"] == "0.15000000"
    assert first["current"]["status"] == "current"
    assert first["current"]["can_delete"] is False
    assert second["current"]["id"] == current.pk
    assert second["current"]["source"] == "seed"
    assert second["current"]["created_by"] is None
    assert second["scheduled"]["id"] == scheduled.pk
    assert second["scheduled"]["status"] == "scheduled"
    assert second["scheduled"]["can_delete"] is True
    assert second["scheduled"]["input_token_price_per_1m"] == "1.50000000"


def test_created_by_falls_back_to_email(superadmin_client):
    user = UserFactory(full_name="")
    AiPricingFactory(created_by=user)
    row = superadmin_client.get(LIST_URL).json()["results"][0]["current"]
    assert row["created_by"] == {"id": user.pk, "name": user.email}


def test_list_paginates(superadmin_client):
    for i in range(3):
        AiPricingFactory(model=f"m{i}")
    body = superadmin_client.get(LIST_URL, {"page_size": 2}).json()
    assert body["count"] == 3
    assert len(body["results"]) == 2
    assert body["next"] is not None


def test_history_ascending_with_statuses(superadmin_client):
    past, current, scheduled = _scheduled_pair("gpt-x")
    AiPricingFactory(model="other")
    body = superadmin_client.get(HISTORY_URL, {"model": "gpt-x"}).json()
    assert [r["id"] for r in body["results"]] == [past.pk, current.pk, scheduled.pk]
    assert [r["status"] for r in body["results"]] == ["past", "current", "scheduled"]
    assert [r["can_delete"] for r in body["results"]] == [False, False, True]
    assert set(body["results"][0]) == ROW_KEYS


def test_history_requires_model(superadmin_client):
    assert superadmin_client.get(HISTORY_URL).status_code == 400
    assert superadmin_client.get(HISTORY_URL, {"model": "  "}).status_code == 400


def test_history_unknown_model_is_empty_page(superadmin_client):
    r = superadmin_client.get(HISTORY_URL, {"model": "nope"})
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert r.json()["results"] == []


def test_suggestions_shape_and_filter(superadmin_client):
    AiPricingFactory(model="priced-model")
    AiUsageLogFactory(model="no-price-model")
    body = superadmin_client.get(SUGGEST_URL).json()
    assert set(body) == {"results"}
    by_model = {s["model"]: s for s in body["results"]}
    assert set(by_model["priced-model"]) == {"model", "last_used_at", "has_price"}
    assert by_model["priced-model"]["has_price"] is True
    assert by_model["no-price-model"]["has_price"] is False
    assert by_model["no-price-model"]["last_used_at"] is not None
    assert body["results"][0]["model"] == "no-price-model"
    filtered = superadmin_client.get(SUGGEST_URL, {"q": "PRICED-M"}).json()["results"]
    assert [s["model"] for s in filtered] == ["priced-model"]


def test_suggestions_capped_at_20(superadmin_client):
    for i in range(25):
        AiPricingFactory(model=f"m{i:02d}")
    assert len(superadmin_client.get(SUGGEST_URL).json()["results"]) == 20


def test_missing_returns_unpriced_used_model(superadmin_client, settings):
    settings.OPENAI_MODEL = "configured-model"
    AiPricingFactory(model="configured-model")
    AiUsageLogFactory(model="used-model")
    body = superadmin_client.get(MISSING_URL).json()
    assert set(body) == {"models", "generated_at"}
    assert [m["model"] for m in body["models"]] == ["used-model"]
    assert set(body["models"][0]) == {"model", "last_used_at", "configured"}
    assert body["models"][0]["configured"] is False


def test_missing_flags_configured_model(superadmin_client, settings):
    settings.OPENAI_MODEL = "configured-model"
    body = superadmin_client.get(MISSING_URL).json()
    assert body["models"] == [
        {"model": "configured-model", "last_used_at": None, "configured": True}
    ]


def test_refresh_recomputes_after_cached_read(superadmin_client, settings):
    settings.OPENAI_MODEL = "configured-model"
    assert len(superadmin_client.get(MISSING_URL).json()["models"]) == 1  # warms the cache
    AiPricingFactory(model="configured-model")  # bypasses the service: cache stays warm
    assert len(superadmin_client.get(MISSING_URL).json()["models"]) == 1
    r = superadmin_client.post(REFRESH_URL)
    assert r.status_code == 200
    assert r.json()["models"] == []
    assert superadmin_client.get(MISSING_URL).json()["models"] == []


def test_refresh_is_throttled(db, settings):
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["superadmin_ai_pricing_refresh"] == "1/minute"
    assert rates["superadmin_ai_pricing_read"] == "120/minute"
    assert rates["superadmin_ai_pricing_write"] == "30/minute"
    client = APIClient()
    client.force_authenticate(UserFactory(role=User.Role.SUPERADMIN))
    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
        first = client.post(REFRESH_URL)
        second = client.post(REFRESH_URL)
    assert first.status_code == 200
    assert second.status_code == 429


def _count(client, url, params=None):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url, params).status_code == 200
    return len(ctx.captured_queries)


def _seed(n, start=0):
    user = UserFactory(full_name="U")
    for i in range(start, start + n):
        AiPricingFactory(model=f"m{i:03d}", created_by=user)
        AiUsageLogFactory(model=f"used{i:03d}")
    for k in range(n):  # history rows for one model
        AiPricingFactory(
            model="hist",
            effective_from=PAST + timedelta(days=k + start),
            effective_to=PAST + timedelta(days=k + start + 1),
            created_by=user,
        )


@pytest.mark.parametrize(
    ("url", "params", "ceiling"),
    [
        (LIST_URL, None, 4),
        (HISTORY_URL, {"model": "hist"}, 4),
        (SUGGEST_URL, None, 5),
        (MISSING_URL, None, 5),
    ],
)
def test_query_count_is_independent_of_row_count(superadmin_client, url, params, ceiling):
    _seed(3)
    small = _count(superadmin_client, url, params)
    _seed(27, start=3)  # 30 models total
    cache.clear()
    large = _count(superadmin_client, url, params)
    assert large == small
    assert large <= ceiling


# ---------------------------------------------------------------- write APIs


def _detail_url(pk):
    return reverse("superadmin-ai-pricing-detail", args=[pk])


def _payload(**over):
    body = {
        "model": "gpt-new",
        "input_token_price_per_1m": "1.50000000",
        "output_token_price_per_1m": "6.00000000",
        "cached_token_price_per_1m": "0.75000000",
        "effective_from": (timezone.now() + timedelta(days=2)).isoformat(),
    }
    body.update(over)
    return body


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_non_superadmin_cannot_write(db, factory):
    row = AiPricingFactory(effective_from=timezone.now() + timedelta(days=3), effective_to=None)
    c = APIClient()
    c.force_authenticate(factory())
    assert c.post(LIST_URL, _payload(), format="json").status_code == 403
    assert c.delete(_detail_url(row.pk)).status_code == 403
    assert AiPricing.objects.filter(pk=row.pk).exists()


def test_anonymous_cannot_write(db):
    assert APIClient().post(LIST_URL, _payload(), format="json").status_code in (401, 403)
    assert APIClient().delete(_detail_url(1)).status_code in (401, 403)


def test_post_creates_scheduled_row_with_audit(superadmin_client):
    r = superadmin_client.post(LIST_URL, _payload(model="  gpt-new  "), format="json")
    assert r.status_code == 201
    body = r.json()
    assert set(body) == ROW_KEYS
    assert body["model"] == "gpt-new"
    assert body["input_token_price_per_1m"] == "1.50000000"
    assert body["status"] == "scheduled"
    assert body["can_delete"] is True
    assert body["source"] == "manual"
    row = AiPricing.objects.get(pk=body["id"])
    assert row.created_by is not None
    assert body["created_by"]["id"] == row.created_by_id
    from apps.common.models import AuditLog

    log = AuditLog.objects.get(entity_type="ai_pricing", entity_id=str(row.pk))
    assert log.organisation_id is None
    assert log.actor_id == row.created_by_id
    assert log.action == "ai_pricing.added"


def test_post_immediate_price_closes_open_row(superadmin_client):
    old = AiPricingFactory(model="gpt-new", effective_from=PAST, effective_to=None)
    r = superadmin_client.post(
        LIST_URL, _payload(effective_from=timezone.now().isoformat()), format="json"
    )
    assert r.status_code == 201
    assert r.json()["status"] == "current"
    old.refresh_from_db()
    assert old.effective_to is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("input_token_price_per_1m", "-0.00000001"),
        ("output_token_price_per_1m", "1000.00000001"),
        ("cached_token_price_per_1m", "0.123456789"),
        ("input_token_price_per_1m", "abc"),
        ("effective_from", "not-a-date"),
        ("model", ""),
        ("model", "   "),
        ("model", "x" * 101),
    ],
)
def test_post_validation_errors(superadmin_client, field, value):
    r = superadmin_client.post(LIST_URL, _payload(**{field: value}), format="json")
    assert r.status_code == 400
    assert field in r.json()
    assert not AiPricing.objects.exists()


def test_post_missing_fields_400(superadmin_client):
    r = superadmin_client.post(LIST_URL, {}, format="json")
    assert r.status_code == 400
    assert set(r.json()) == {
        "model",
        "input_token_price_per_1m",
        "output_token_price_per_1m",
        "cached_token_price_per_1m",
        "effective_from",
    }


def test_post_accepts_boundary_prices(superadmin_client):
    r = superadmin_client.post(
        LIST_URL,
        _payload(input_token_price_per_1m="0", output_token_price_per_1m="1000.00000000"),
        format="json",
    )
    assert r.status_code == 201


def test_post_backdated_400(superadmin_client):
    r = superadmin_client.post(
        LIST_URL,
        _payload(effective_from=(timezone.now() - timedelta(hours=1)).isoformat()),
        format="json",
    )
    assert r.status_code == 400
    assert r.json()["code"] == "backdated"
    assert isinstance(r.json()["detail"], str)
    assert not AiPricing.objects.exists()


def test_post_second_scheduled_409(superadmin_client):
    AiPricingFactory(model="gpt-new", effective_from=PAST, effective_to=None)
    assert superadmin_client.post(LIST_URL, _payload(), format="json").status_code == 201
    r = superadmin_client.post(
        LIST_URL,
        _payload(effective_from=(timezone.now() + timedelta(days=9)).isoformat()),
        format="json",
    )
    assert r.status_code == 409
    assert r.json()["code"] == "scheduled_price_exists"
    assert AiPricing.objects.filter(model="gpt-new").count() == 2


def test_post_concurrent_change_maps_to_409(superadmin_client):
    from apps.integrations.openai.services.pricing_management import ConcurrentPriceChangeError

    with patch(
        "apps.integrations.openai.pricing_views.add_price", side_effect=ConcurrentPriceChangeError
    ):
        r = superadmin_client.post(LIST_URL, _payload(), format="json")
    assert r.status_code == 409
    assert r.json()["code"] == "concurrent_change"


def test_post_service_value_error_maps_to_400(superadmin_client):
    with patch("apps.integrations.openai.pricing_views.add_price", side_effect=ValueError("x")):
        r = superadmin_client.post(LIST_URL, _payload(), format="json")
    assert r.status_code == 400
    assert r.json() == {"model": ["This field may not be blank."]}


def test_delete_scheduled_reopens_previous(superadmin_client):
    from apps.common.models import AuditLog

    _, current, scheduled = _scheduled_pair("gpt-x")
    r = superadmin_client.delete(_detail_url(scheduled.pk))
    assert r.status_code == 204
    assert r.content == b""
    assert not AiPricing.objects.filter(pk=scheduled.pk).exists()
    current.refresh_from_db()
    assert current.effective_to is None
    log = AuditLog.objects.get(entity_type="ai_pricing", action="ai_pricing.deleted")
    assert log.organisation_id is None
    assert log.entity_id == str(scheduled.pk)


def test_delete_current_409(superadmin_client):
    _, current, _ = _scheduled_pair("gpt-x")
    r = superadmin_client.delete(_detail_url(current.pk))
    assert r.status_code == 409
    assert r.json()["code"] == "price_not_scheduled"
    assert AiPricing.objects.filter(pk=current.pk).exists()


def test_delete_unknown_404(superadmin_client):
    assert superadmin_client.delete(_detail_url(999999)).status_code == 404


def test_write_invalidates_missing_cache(
    superadmin_client, settings, django_capture_on_commit_callbacks
):
    settings.OPENAI_MODEL = "gpt-new"
    assert len(superadmin_client.get(MISSING_URL).json()["models"]) == 1
    with django_capture_on_commit_callbacks(execute=True):
        superadmin_client.post(
            LIST_URL, _payload(effective_from=timezone.now().isoformat()), format="json"
        )
    assert superadmin_client.get(MISSING_URL).json()["models"] == []


def test_throttle_scopes_are_per_method(db, settings):
    rates = dict(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
    rates["superadmin_ai_pricing_write"] = "1/minute"
    client = APIClient()
    client.force_authenticate(UserFactory(role=User.Role.SUPERADMIN))
    with patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
        assert client.get(LIST_URL).status_code == 200  # read scope unaffected by write limit
        assert client.get(LIST_URL).status_code == 200
        assert client.post(LIST_URL, _payload(), format="json").status_code == 201
        assert client.post(LIST_URL, _payload(model="other"), format="json").status_code == 429
        assert client.delete(_detail_url(1)).status_code == 429


def test_write_query_ceilings(superadmin_client):
    _seed(10)
    with CaptureQueriesContext(connection) as ctx:
        r = superadmin_client.post(LIST_URL, _payload(), format="json")
    assert r.status_code == 201
    assert len(ctx.captured_queries) <= 8
    with CaptureQueriesContext(connection) as ctx:
        assert superadmin_client.delete(_detail_url(r.json()["id"])).status_code == 204
    assert len(ctx.captured_queries) <= 8


# --- Page shell (Task 7) ---


def test_pricing_page_renders_for_superadmin(client, db):
    client.force_login(UserFactory(role=User.Role.SUPERADMIN))
    resp = client.get("/admin/ai-pricing/")
    assert resp.status_code == 200
    assert b'id="ai-pricing-root"' in resp.content
    assert reverse("ai_pricing_page") == "/admin/ai-pricing/"


@pytest.mark.parametrize("factory", [OrgAdminFactory, StaffAdminFactory])
def test_pricing_page_forbidden_for_tenants(client, db, factory):
    client.force_login(factory())
    assert client.get("/admin/ai-pricing/").status_code == 403


def test_pricing_page_redirects_anonymous(client, db):
    assert client.get("/admin/ai-pricing/").status_code == 302


def test_sidebar_shows_ai_pricing_only_for_superadmin(client, db):
    from apps.organisations.tests.factories import OrganisationFactory

    client.force_login(UserFactory(role=User.Role.SUPERADMIN))
    assert b'href="/admin/ai-pricing/"' in client.get("/admin/ai-pricing/").content
    client.logout()
    client.force_login(OrgAdminFactory(organisation=OrganisationFactory()))
    resp = client.get("/admin/org/shops/")
    assert resp.status_code == 200
    assert b"/admin/ai-pricing/" not in resp.content
