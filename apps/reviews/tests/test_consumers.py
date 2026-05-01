"""INFRA-09: SyncProgressConsumer auth + tenant scope rules.

Tests cover:
  - Anonymous user -> 4401
  - Authenticated user from a different organisation -> 4403
  - Authenticated user from the same organisation as the shop -> accepted
  - Disconnect cleans up the channel group
  - progress_event relays the payload to the client
"""

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.tests.factories import ShopFactory
from config.routing import websocket_urlpatterns

# Test directly against the URL router so we control scope injection.
test_application = URLRouter(websocket_urlpatterns)

pytestmark = pytest.mark.django_db(transaction=True)


async def _make_communicator(shop_id: int, user: object) -> WebsocketCommunicator:
    communicator = WebsocketCommunicator(test_application, f"/ws/sync-progress/{shop_id}/")
    communicator.scope["user"] = user
    # Ensure url_route kwargs are populated with the integer shop_id.
    communicator.scope.setdefault("url_route", {"kwargs": {"shop_id": shop_id}})
    return communicator


async def test_anonymous_connection_rejected_4401() -> None:
    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)

    communicator = await _make_communicator(shop.pk, AnonymousUser())
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4401


async def test_cross_tenant_connection_rejected_4403() -> None:
    org_a = await sync_to_async(OrganisationFactory)()
    org_b = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org_a)
    user_b = await sync_to_async(UserFactory)(organisation=org_b)

    communicator = await _make_communicator(shop.pk, user_b)
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4403


async def test_authenticated_same_tenant_connection_accepted() -> None:
    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    communicator = await _make_communicator(shop.pk, user)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


async def test_disconnect_cleans_up_group() -> None:
    from unittest.mock import AsyncMock, patch

    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    communicator = await _make_communicator(shop.pk, user)
    with patch(
        "channels.layers.InMemoryChannelLayer.group_discard",
        new=AsyncMock(),
    ) as discard:
        await communicator.connect()
        await communicator.disconnect()
        assert discard.await_count >= 1


async def test_progress_event_relays_payload() -> None:
    from channels.layers import get_channel_layer

    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    communicator = await _make_communicator(shop.pk, user)
    await communicator.connect()

    layer = get_channel_layer()
    await layer.group_send(
        f"sync-progress-{shop.pk}",
        {"type": "progress.event", "payload": {"type": "sync.fetch.progress", "fetched": 10}},
    )
    msg = await communicator.receive_json_from(timeout=2)
    assert msg == {"type": "sync.fetch.progress", "fetched": 10}
    await communicator.disconnect()
