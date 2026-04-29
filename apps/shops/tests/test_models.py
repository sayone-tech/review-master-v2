from __future__ import annotations

import pytest
from django.db import connection

from apps.shops.models import Shop, ShopAuditLog
from apps.shops.tests.factories import ShopAuditLogFactory, ShopFactory

pytestmark = pytest.mark.django_db


def test_shop_defaults() -> None:
    shop = ShopFactory(name="Main Street")
    assert shop.connection_method == Shop.ConnectionMethod.NOT_CONNECTED
    assert shop.connection_status == Shop.ConnectionStatus.NOT_CONNECTED
    assert shop.is_active is True
    assert str(shop) == "Main Street"


def test_shop_encrypted_fields_round_trip() -> None:
    shop = ShopFactory(google_refresh_token="secret-token-abc", api_key="my-api-key-123")
    shop.refresh_from_db()
    assert shop.google_refresh_token == "secret-token-abc"
    assert shop.api_key == "my-api-key-123"


def test_shop_api_key_stored_as_ciphertext() -> None:
    """Verify the raw DB column does NOT contain the plaintext value."""
    shop = ShopFactory(api_key="plaintext-key-xyz")
    with connection.cursor() as cursor:
        cursor.execute("SELECT api_key FROM shops_shop WHERE id = %s", [shop.pk])
        raw_value = cursor.fetchone()[0]
    assert raw_value != "plaintext-key-xyz", "api_key must be ciphertext, not plaintext"
    assert "plaintext-key-xyz" not in str(raw_value)


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
