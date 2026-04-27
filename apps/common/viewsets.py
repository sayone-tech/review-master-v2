from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rest_framework.viewsets import GenericViewSet

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TenantScopedViewSet(GenericViewSet[Any]):
    """Base for ALL Org Admin and Staff Admin DRF viewsets.

    Filters every get_queryset() to the authenticated user's organisation.
    Superadmin viewsets MUST NOT inherit this class.

    NEVER override get_queryset() without calling super() first, and NEVER
    remove the organisation_id filter without an explicit comment.
    """

    def get_queryset(self) -> QuerySet:  # type: ignore[type-arg]
        qs = super().get_queryset()
        org_id = getattr(self.request.user, "organisation_id", None)
        if org_id is None:
            return qs.none()
        return qs.filter(organisation_id=org_id)
