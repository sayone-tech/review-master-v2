from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User


class IsSuperadmin(BasePermission):
    """Allow only authenticated users whose role is SUPERADMIN."""

    message = "Superadmin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, "role", None) == User.Role.SUPERADMIN)
