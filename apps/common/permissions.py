from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User


class IsOrgScoped(BasePermission):
    """Allow ORG_ADMIN or STAFF_ADMIN with an organisation.

    CRITICAL: Implements has_object_permission to prevent IDOR on detail/mutation
    endpoints. DRF's default has_object_permission returns True; without this
    override, an Org Admin could PATCH/DELETE objects belonging to other orgs
    even when get_queryset() is correctly scoped.
    """

    message = "Organisation membership required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(user, "role", None)
        if role not in (User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN):
            return False
        return bool(getattr(user, "organisation_id", None) is not None)

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        """Verify the object belongs to the requesting user's organisation."""
        user = request.user
        obj_org_id = getattr(obj, "organisation_id", None)
        if obj_org_id is None:
            return False
        return bool(obj_org_id == getattr(user, "organisation_id", None))


class RequiresSessionAuth(BasePermission):
    """Grant access only to requests authenticated via Django's SessionAuthentication.

    JWT-authenticated requests (mobile clients) and unauthenticated requests are
    both denied with a 403.  This prevents mobile API tokens from being used
    against browser-only mutation endpoints.
    """

    message = "This action is only available via the web application."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.successful_authenticator, SessionAuthentication)
