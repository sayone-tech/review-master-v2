"""SyncProgressConsumer — single Phase 11 WebSocket consumer.

Auth + tenant scoping per CLAUDE.md §13.4:
  - Unauthenticated  -> close(4401)
  - Cross-tenant     -> close(4403)
  - Same tenant      -> accept, join group, send Redis snapshot

Phase 11: tenant check tightened to staff-scope (StaffAccessScope filter for
STAFF_ADMIN role). ORG_ADMIN users continue to access all shops in their org.

See CLAUDE.md §13.2 — this is the ONLY consumer in Phase 11. Adding more
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
        """Phase 11: org-level scope for ORG_ADMIN, StaffAccessScope for STAFF_ADMIN.

        Returns True when:
          - User's organisation_id matches the shop's organisation_id, AND
          - If role is STAFF_ADMIN: the user has a SHOP scope for this shop OR a
            REGION scope covering the shop's region.

        Returns False otherwise.
        """
        from apps.accounts.models import StaffAccessScope, User
        from apps.shops.models import Shop

        try:
            shop = Shop.objects.only("organisation_id", "region_id").get(pk=shop_id)
        except Shop.DoesNotExist:
            return False

        user_org_id = getattr(user, "organisation_id", None)
        if user_org_id is None or shop.organisation_id != user_org_id:
            return False

        role = getattr(user, "role", None)
        if role != User.Role.STAFF_ADMIN:
            # Org Admins (and any other role with this org_id) can access all shops in their org.
            return True

        # STAFF_ADMIN: must have an explicit shop or region scope covering this shop.
        user_pk: int = user.pk
        has_shop_scope = StaffAccessScope.objects.filter(
            user_id=user_pk,
            scope_type=StaffAccessScope.ScopeType.SHOP,
            shop_id=shop_id,
        ).exists()
        if has_shop_scope:
            return True
        region_id: int | None = shop.region_id
        if region_id is None:
            return False
        return StaffAccessScope.objects.filter(
            user_id=user_pk,
            scope_type=StaffAccessScope.ScopeType.REGION,
            region_id=region_id,
        ).exists()
