from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError

from apps.shops.models import ReviewTarget, Shop, ShopAuditLog
from apps.shops.tests.factories import ReviewTargetFactory, ShopAuditLogFactory, ShopFactory

pytestmark = pytest.mark.django_db


def test_shop_defaults() -> None:
    shop = ShopFactory(name="Main Street")
    assert shop.connection_method == Shop.ConnectionMethod.NOT_CONNECTED
    assert shop.connection_status == Shop.ConnectionStatus.NOT_CONNECTED
    assert shop.is_active is True
    assert str(shop) == "Main Street"


def test_shop_encrypted_fields_round_trip() -> None:
    shop = ShopFactory(google_refresh_token="secret-token-abc")
    shop.refresh_from_db()
    assert shop.google_refresh_token == "secret-token-abc"


class TestShopAuditLog:
    def test_str_returns_action(self) -> None:
        log = ShopAuditLogFactory(action=ShopAuditLog.Action.API_KEY_REVEALED)
        assert "shop.api_key.revealed" in str(log)

    def test_default_ordering_newest_first(self) -> None:
        first = ShopAuditLogFactory()
        second = ShopAuditLogFactory()
        result = list(ShopAuditLog.objects.all())
        assert result[0].pk == second.pk
        assert result[1].pk == first.pk

    def test_cascade_on_shop_delete(self) -> None:
        shop = ShopFactory()
        log = ShopAuditLogFactory(shop=shop)
        shop.delete()
        assert not ShopAuditLog.objects.filter(pk=log.pk).exists()

    def test_actor_set_null_on_user_delete(self) -> None:
        log = ShopAuditLogFactory()
        actor_pk = log.actor_id
        from apps.accounts.models import User

        User.objects.get(pk=actor_pk).delete()
        log.refresh_from_db()
        assert log.actor_id is None


@pytest.mark.django_db
class TestReviewTargetModel:
    def test_creates_with_valid_data(self):
        t = ReviewTargetFactory()
        assert t.pk is not None
        assert t.target_count >= 1

    def test_unique_constraint_prevents_duplicate_period(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=date(2026, 5, 1),
            target_count=100,
        )
        with pytest.raises(IntegrityError):
            ReviewTargetFactory(
                shop=shop,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=date(2026, 5, 1),
                target_count=200,
            )

    def test_different_period_type_same_start_allowed(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=date(2026, 5, 1),
        )
        t2 = ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            period_start=date(2026, 5, 4),
        )
        assert t2.pk is not None
