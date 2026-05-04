"""Phase 13 plan 05 — Notification REST API.

Three endpoints scoped to ``request.user`` (no cross-user reads):
  - GET  /api/v1/notifications/bell/           NOTF-01 / NOTF-04 (poll source)
  - POST /api/v1/notifications/{pk}/read/      NOTF-03
  - POST /api/v1/notifications/mark-all-read/  NOTF-03

The bell endpoint is the hot path — polled every 60s by Plan 13-08's NotifBell.
It MUST stay inside a small SQL budget (one count + one select). The composite
index (recipient, is_read, created_at) on Notification covers both.
"""

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.permissions import IsOrgScoped
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationReadSerializer


class NotificationViewSet(viewsets.GenericViewSet[Notification]):
    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = NotificationReadSerializer
    queryset = Notification.objects.none()

    def get_queryset(self) -> QuerySet[Notification]:
        # Tenant scope: a Notification row's `recipient` is the only authoritative
        # subject — filtering by request.user covers org boundaries because
        # dispatch_notification only writes rows for users in the same org.
        return (
            Notification.objects.filter(recipient=self.request.user)  # type: ignore[misc]
            .select_related("shop")
            .order_by("-created_at")
        )

    @action(detail=False, methods=["get"], url_path="bell")
    def bell(self, request: Request) -> Response:
        """NOTF-01 / NOTF-04: ``{unread_count, items}`` for the bell popover.

        Hot path — polled every 60 s. ≤ 3 SQL queries (auth, count, select).
        """
        qs = self.get_queryset().filter(is_read=False)
        unread_count = qs.count()
        items = list(qs[:10])
        return Response(
            {
                "unread_count": unread_count,
                "items": NotificationReadSerializer(items, many=True).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        """NOTF-03: Mark a single notification read. Idempotent."""
        if pk is None:
            return Response({"detail": "Not found"}, status=404)
        n = self.get_queryset().filter(pk=pk).first()
        if n is None:
            return Response({"detail": "Not found"}, status=404)
        if not n.is_read:
            n.is_read = True
            n.save(update_fields=["is_read", "updated_at"])
        return Response({"id": n.pk, "is_read": True})

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request: Request) -> Response:
        """NOTF-03: Mark every unread notification for the current user as read."""
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "ok"})
