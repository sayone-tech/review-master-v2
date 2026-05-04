"""Phase 13 plan 03 — Action item RBAC permissions.

BrandScopeGuard implements Layer 2 of the three-layer Staff scope
(CLAUDE.md §9). It protects detail/mutation endpoints from direct-URL
bypasses where a Staff user crafts a request for a known BRAND-scope
ActionItem id. Layer 1 (selector filter) prevents the item from showing
in lists; Layer 2 enforces 403 on direct access.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.action_items.models import ActionItem


class BrandScopeGuard(BasePermission):
    """Block STAFF_ADMIN from BRAND-scoped action items on detail/mutation endpoints."""

    message = "Brand-scoped action items are not accessible to Staff."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        user = request.user
        return not (
            getattr(user, "role", None) == "STAFF_ADMIN"
            and getattr(obj, "scope", None) == ActionItem.Scope.BRAND
        )
