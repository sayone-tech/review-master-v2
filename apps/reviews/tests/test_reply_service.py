"""Phase 11 — Reply service + endpoint tests."""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import OrgAdminFactory
from apps.common.models import AuditLog
from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleReplyError,
    GoogleUnreachableError,
)
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.exceptions import ReplyConflictError, ReplyFailedError
from apps.reviews.services import replies as replies_mod
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.models import Shop
from apps.shops.tests.factories import ShopFactory

pytestmark = pytest.mark.django_db


@contextlib.contextmanager
def _lock_acquired():
    @contextlib.contextmanager
    def _ctx(_key: str, timeout: int = 30):
        yield True

    with patch.object(replies_mod, "distributed_lock", _ctx):
        yield


@contextlib.contextmanager
def _lock_held():
    @contextlib.contextmanager
    def _ctx(_key: str, timeout: int = 30):
        yield False

    with patch.object(replies_mod, "distributed_lock", _ctx):
        yield


def _make_shop(**kwargs):
    shop = ShopFactory(
        connection_status=Shop.ConnectionStatus.CONNECTED,
        google_refresh_token="rt",
        **kwargs,
    )
    Shop.objects.filter(pk=shop.pk).update(
        google_account_name="accounts/123",
        google_location_name="accounts/123/locations/456",
    )
    shop.refresh_from_db()
    return shop


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------


def test_submit_reply_success_persists_and_audits() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop, is_replied=False)
    user = OrgAdminFactory(organisation=shop.organisation)
    with (
        _lock_acquired(),
        patch.object(replies_mod, "_refresh_access_token", return_value="token"),
        patch.object(
            replies_mod,
            "post_reply",
            return_value={"comment": "Thanks!", "updateTime": "2026-05-01T12:00:00Z"},
        ),
    ):
        replies_mod.submit_reply(review=review, comment="Thanks!", actor=user)
    review.refresh_from_db()
    assert review.is_replied is True
    assert review.reply_comment == "Thanks!"
    assert AuditLog.objects.filter(
        entity_type="review", entity_id=str(review.pk), action="reply_posted"
    ).exists()


def test_submit_reply_failure_does_not_mutate_review() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop, is_replied=False)
    user = OrgAdminFactory(organisation=shop.organisation)
    with (
        _lock_acquired(),
        patch.object(replies_mod, "_refresh_access_token", return_value="token"),
        patch.object(
            replies_mod,
            "post_reply",
            side_effect=GoogleReplyError(status=400, body="bad"),
        ),
        pytest.raises(ReplyFailedError) as exc,
    ):
        replies_mod.submit_reply(review=review, comment="x", actor=user)
    assert exc.value.code == "reply_rejected"
    review.refresh_from_db()
    assert review.is_replied is False
    assert review.reply_comment == ""
    assert AuditLog.objects.filter(
        entity_type="review", entity_id=str(review.pk), action="reply_failed"
    ).exists()


def test_submit_reply_invalid_grant_marks_shop_expired() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    with (
        _lock_acquired(),
        patch.object(
            replies_mod,
            "_refresh_access_token",
            side_effect=GoogleAuthError(reason="invalid_grant"),
        ),
        pytest.raises(ReplyFailedError) as exc,
    ):
        replies_mod.submit_reply(review=review, comment="x", actor=user)
    assert exc.value.code == "invalid_grant"
    shop.refresh_from_db()
    assert shop.connection_status == Shop.ConnectionStatus.EXPIRED


def test_submit_reply_conflict_when_lock_held() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    with _lock_held(), pytest.raises(ReplyConflictError):
        replies_mod.submit_reply(review=review, comment="x", actor=user)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_reply_endpoint_success_returns_updated_review() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop, is_replied=False)
    user = OrgAdminFactory(organisation=shop.organisation)
    client = APIClient()
    client.force_authenticate(user=user)
    with (
        _lock_acquired(),
        patch.object(replies_mod, "_refresh_access_token", return_value="token"),
        patch.object(
            replies_mod,
            "post_reply",
            return_value={"comment": "Thanks!", "updateTime": "2026-05-01T12:00:00Z"},
        ),
    ):
        resp = client.post(
            f"/api/v1/reviews/{review.pk}/reply/",
            {"comment": "Thanks!"},
            format="json",
        )
    assert resp.status_code == 200
    assert resp.data["is_replied"] is True
    assert resp.data["reply_comment"] == "Thanks!"


def test_reply_endpoint_validation_error_on_empty_comment() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        f"/api/v1/reviews/{review.pk}/reply/",
        {"comment": ""},
        format="json",
    )
    assert resp.status_code == 400


def test_reply_endpoint_502_on_google_failure() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    client = APIClient()
    client.force_authenticate(user=user)
    with (
        _lock_acquired(),
        patch.object(replies_mod, "_refresh_access_token", return_value="token"),
        patch.object(replies_mod, "post_reply", side_effect=GoogleUnreachableError()),
    ):
        resp = client.post(
            f"/api/v1/reviews/{review.pk}/reply/",
            {"comment": "Thanks"},
            format="json",
        )
    assert resp.status_code == 502
    assert resp.data["code"] == "unreachable"


def test_reply_endpoint_409_when_lock_held() -> None:
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    client = APIClient()
    client.force_authenticate(user=user)
    with _lock_held():
        resp = client.post(
            f"/api/v1/reviews/{review.pk}/reply/",
            {"comment": "Thanks"},
            format="json",
        )
    assert resp.status_code == 409


def test_reply_endpoint_throttle_after_30_per_minute(settings) -> None:
    """REVW-12: 30 submissions per minute."""
    from django.core.cache import cache

    cache.clear()
    shop = _make_shop()
    review = ReviewFactory(organisation=shop.organisation, shop=shop)
    user = OrgAdminFactory(organisation=shop.organisation)
    client = APIClient()
    client.force_authenticate(user=user)
    with (
        _lock_acquired(),
        patch.object(replies_mod, "_refresh_access_token", return_value="token"),
        patch.object(
            replies_mod,
            "post_reply",
            return_value={"comment": "x", "updateTime": "2026-05-01T12:00:00Z"},
        ),
    ):
        statuses = []
        for _ in range(31):
            resp = client.post(
                f"/api/v1/reviews/{review.pk}/reply/",
                {"comment": "Thanks!"},
                format="json",
            )
            statuses.append(resp.status_code)
    cache.clear()
    assert 429 in statuses


def test_reply_endpoint_cross_org_returns_404() -> None:
    """ReviewViewSet inherits TenantScopedViewSet so other-org reviews 404."""
    shop_a = _make_shop()
    review_a = ReviewFactory(organisation=shop_a.organisation, shop=shop_a)
    other_org = OrganisationFactory()
    other_user = OrgAdminFactory(organisation=other_org)
    client = APIClient()
    client.force_authenticate(user=other_user)
    resp = client.post(
        f"/api/v1/reviews/{review_a.pk}/reply/",
        {"comment": "Hi"},
        format="json",
    )
    assert resp.status_code == 404
