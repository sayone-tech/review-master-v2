"""SyncProgressConsumer — single Phase 10 WebSocket consumer.

Auth + tenant scoping per CLAUDE.md §13.4:
  - Unauthenticated  -> close(4401)
  - Cross-tenant     -> close(4403)
  - Same tenant      -> accept, join group, send Redis snapshot

Phase 10: tenant check is org-level (user.organisation_id == shop.organisation_id).
Phase 11 will tighten to staff-scope (StaffAccessScope filter for STAFF_ADMIN role).

See CLAUDE.md §13.2 — this is the ONLY consumer in Phase 10. Adding more
requires updating CLAUDE.md §13 first.
"""

from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.reviews.selectors.sync_progress import get_progress_snapshot


class SyncProgressConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    async def connect(self) -> None:
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        shop_id = self.scope["url_route"]["kwargs"]["shop_id"]
        if not await self._user_can_access_shop(user, shop_id):
            await self.close(code=4403)
            return
        self.group = f"sync-progress-{shop_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        snapshot = await get_progress_snapshot(shop_id=shop_id)
        if snapshot:
            await self.send_json(snapshot)

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def progress_event(self, event: dict[str, Any]) -> None:
        await self.send_json(event["payload"])

    @database_sync_to_async  # type: ignore[misc]
    def _user_can_access_shop(self, user: Any, shop_id: Any) -> bool:
        """Phase 10: org-level tenant scoping.

        Returns True when the user's organisation_id matches the shop's
        organisation_id. Phase 11 tightens this to staff-scope filtering.
        """
        from apps.shops.models import Shop

        try:
            shop = Shop.objects.only("organisation_id").get(pk=shop_id)
        except Shop.DoesNotExist:
            return False
        user_org_id = getattr(user, "organisation_id", None)
        return user_org_id is not None and shop.organisation_id == user_org_id
