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


# -------------------------------------------------------------------------
# Phase 11 — staff-scope rejection + snapshot-on-connect
# -------------------------------------------------------------------------


async def test_staff_user_without_scope_rejected_4403() -> None:
    from apps.accounts.models import User
    from apps.regions.tests.factories import RegionFactory

    org = await sync_to_async(OrganisationFactory)()
    region = await sync_to_async(RegionFactory)(organisation=org)
    shop = await sync_to_async(ShopFactory)(organisation=org, region=region)
    staff_user = await sync_to_async(UserFactory)(organisation=org, role=User.Role.STAFF_ADMIN)

    communicator = await _make_communicator(shop.pk, staff_user)
    connected, code = await communicator.connect()
    assert connected is False
    assert code == 4403


async def test_staff_user_with_shop_scope_accepted() -> None:
    from apps.accounts.models import StaffAccessScope, User
    from apps.regions.tests.factories import RegionFactory

    org = await sync_to_async(OrganisationFactory)()
    region = await sync_to_async(RegionFactory)(organisation=org)
    shop = await sync_to_async(ShopFactory)(organisation=org, region=region)
    staff_user = await sync_to_async(UserFactory)(organisation=org, role=User.Role.STAFF_ADMIN)
    await sync_to_async(StaffAccessScope.objects.create)(
        user=staff_user,
        scope_type=StaffAccessScope.ScopeType.SHOP,
        shop=shop,
    )

    communicator = await _make_communicator(shop.pk, staff_user)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


async def test_staff_user_with_region_scope_accepted() -> None:
    from apps.accounts.models import StaffAccessScope, User
    from apps.regions.tests.factories import RegionFactory

    org = await sync_to_async(OrganisationFactory)()
    region = await sync_to_async(RegionFactory)(organisation=org)
    shop = await sync_to_async(ShopFactory)(organisation=org, region=region)
    staff_user = await sync_to_async(UserFactory)(organisation=org, role=User.Role.STAFF_ADMIN)
    await sync_to_async(StaffAccessScope.objects.create)(
        user=staff_user,
        scope_type=StaffAccessScope.ScopeType.REGION,
        region=region,
    )

    communicator = await _make_communicator(shop.pk, staff_user)
    connected, _ = await communicator.connect()
    assert connected is True
    await communicator.disconnect()


async def test_snapshot_sent_on_connect_when_progress_exists() -> None:
    from unittest.mock import patch

    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    fake_snapshot = {
        "shop_id": shop.pk,
        "status": "fetching",
        "fetched": 12,
        "total_estimate": 100,
    }

    # Patch the underlying Redis-backed reader so we don't need a live Redis.
    with patch(
        "apps.reviews.services.progress.read_progress_snapshot",
        return_value=fake_snapshot,
    ):
        communicator = await _make_communicator(shop.pk, user)
        connected, _ = await communicator.connect()
        assert connected is True
        msg = await communicator.receive_json_from(timeout=2)
        assert msg == fake_snapshot
        await communicator.disconnect()


async def test_no_snapshot_sent_when_redis_empty() -> None:
    from unittest.mock import patch

    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    with patch(
        "apps.reviews.services.progress.read_progress_snapshot",
        return_value=None,
    ):
        communicator = await _make_communicator(shop.pk, user)
        connected, _ = await communicator.connect()
        assert connected is True
        # No snapshot should arrive — assert nothing in 0.2s timeout.
        received_snapshot = False
        try:
            await communicator.receive_json_from(timeout=0.2)
            received_snapshot = True
        except Exception:  # noqa: S110
            pass  # timeout expected — no snapshot was sent
        assert received_snapshot is False
        # Note: after a timeout, the communicator may be in a cancelled state.
        # We simply assert that no message was received without disconnecting.


# ---------------------------------------------------------------------------
# Phase 23 Task 4 — reconnect repaint (SEED-01): 4-step snapshot pass-through
# ---------------------------------------------------------------------------


async def test_reconnect_snapshot_carries_4step_keys() -> None:
    """On reconnect, the consumer delivers the full 4-step snapshot verbatim.

    The consumer sends whatever get_progress_snapshot returns; get_progress_snapshot
    delegates to read_progress_snapshot with no key filtering. This test seeds a
    snapshot with the Phase 23 step discriminator and per-step counters, connects an
    authenticated in-org user, and asserts the first on-connect message carries every
    4-step field unchanged — confirming the modal's reconnect-repaint path works
    end to end (SEED-01 / T-23-09 cross-tenant: auth/tenant-scope left unchanged).
    """
    from unittest.mock import patch

    org = await sync_to_async(OrganisationFactory)()
    shop = await sync_to_async(ShopFactory)(organisation=org)
    user = await sync_to_async(UserFactory)(organisation=org)

    # A 4-step snapshot mid-way through the finalising phase.
    four_step_snapshot = {
        "shop_id": shop.pk,
        "status": "finalising",
        "step": "finalising",
        "fetched": 120,
        "enriched": 70,
        "vocab_enriched": 50,
        "vocab_total": 50,
        "finalising_processed": 3,
        "finalising_total": 7,
        "last_update_at": "2026-06-11T10:00:00Z",
    }

    with patch(
        "apps.reviews.services.progress.read_progress_snapshot",
        return_value=four_step_snapshot,
    ):
        communicator = await _make_communicator(shop.pk, user)
        connected, _ = await communicator.connect()
        assert connected is True, "Authenticated same-org user must be accepted"

        msg = await communicator.receive_json_from(timeout=2)

        # The consumer must relay the full snapshot verbatim (SEED-01 reconnect repaint).
        assert msg["step"] == "finalising", "step discriminator must be present"
        assert msg["vocab_enriched"] == 50
        assert msg["vocab_total"] == 50
        assert msg["finalising_processed"] == 3
        assert msg["finalising_total"] == 7
        # Core existing fields must survive too (no key stripping).
        assert msg["fetched"] == 120
        assert msg["enriched"] == 70

        await communicator.disconnect()
