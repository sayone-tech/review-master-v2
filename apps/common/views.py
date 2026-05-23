from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSuperadmin
from apps.common.filters import AuditLogFilterSet
from apps.common.models import AuditLog
from apps.common.pagination import AuditLogCursorPagination
from apps.common.permissions import IsOrgScoped
from apps.common.selectors.audit_logs import (
    list_audit_logs_for_org,
    list_audit_logs_for_staff,
)
from apps.common.serializers import AuditLogReadSerializer


class ScalarDocsView(APIView):
    """Interactive API documentation (Scalar) — Superadmin only."""

    permission_classes = [IsSuperadmin]  # noqa: RUF012
    authentication_classes = [SessionAuthentication]  # noqa: RUF012
    renderer_classes = [TemplateHTMLRenderer]  # noqa: RUF012
    template_name = "api_docs/scalar.html"

    def get(self, request: Request) -> Response:
        return Response()


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe — app is running."""
    return JsonResponse({"status": "ok"})


def readyz(request: HttpRequest) -> JsonResponse:
    """Readiness probe — DB reachable, Redis reachable, and all migrations applied."""
    checks: dict[str, str] = {}
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = str(exc)
    try:
        cache.set("readyz_check", "1", 5)
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = str(exc)

    # Verify all migrations have been applied so that dependent services
    # (worker, beat, flower) only start after schema is fully ready.
    if checks.get("db") == "ok":
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            checks["migrations"] = "ok" if not plan else "pending"
        except Exception as exc:
            checks["migrations"] = str(exc)

    status = 200 if all(v == "ok" for v in checks.values()) else 503
    body: dict[str, str] = {"status": "ready" if status == 200 else "degraded", **checks}
    return JsonResponse(body, status=status)


def home(request: HttpRequest) -> HttpResponse:
    """Root URL handler — redirects authenticated users to their role dashboard.

    Unauthenticated users are sent to the login page.
    This replaces the Phase 1 placeholder that accidentally rendered a shell with
    hardcoded /stores/ and /reviews/ sidebar links for ORG_ADMIN users.
    """
    if not request.user.is_authenticated:
        return redirect("login")
    role = getattr(request.user, "role", None)
    if role == "SUPERADMIN":
        return redirect("organisation_list")
    # ORG_ADMIN and STAFF_ADMIN both land on the org dashboard.
    return redirect("org_admin_dashboard_v02")


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    """Branded 404 page (ERR-01). Auth-state detected in template via {% if request.user.is_authenticated %}."""
    return render(request, "404.html", status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    """Branded 500 page (ERR-02). MUST NOT access request.user in Python — template handles auth detection."""
    return render(request, "500.html", status=500)


def showcase(request: HttpRequest) -> HttpResponse:
    """Component showcase page at /__ui__/ — renders every design system primitive."""

    class _FakePaginator:
        count = 47
        page_range = range(1, 6)
        num_pages = 5
        ELLIPSIS = "…"

        def get_elided_page_range(
            self, number: int, *, on_each_side: int = 3, on_ends: int = 2
        ) -> list[int | str]:
            return list(self.page_range)

    class _FakePage:
        number = 1
        paginator = _FakePaginator()

        def start_index(self) -> int:
            return 1

        def end_index(self) -> int:
            return 8

        def has_previous(self) -> bool:
            return False

        def has_next(self) -> bool:
            return True

        def previous_page_number(self) -> int:
            return 1

        def next_page_number(self) -> int:
            return 2

    ctx = {
        "org_type_options": [
            ("", "Select one"),
            ("RETAIL", "Retail"),
            ("RESTAURANT", "Restaurant"),
            ("PHARMACY", "Pharmacy"),
            ("SUPERMARKET", "Supermarket"),
        ],
        "status_options": [("", "All statuses"), ("ACTIVE", "Active"), ("DISABLED", "Disabled")],
        "type_options": [("", "All types"), ("RETAIL", "Retail")],
        "fake_page_obj": _FakePage(),
    }
    return render(request, "pages/showcase.html", ctx)


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Audit log read-only list endpoint (Phase 21).

    Per D-04: ORG_ADMIN sees all org-scoped audit log entries (review reply +
    action_item events); STAFF_ADMIN sees only entries whose entity maps to a
    shop in their StaffAccessScope and SHOP-scope action items.
    Per D-06: Superadmin denied (IsOrgScoped denies role not in ORG/STAFF ADMIN).
    Per D-09: Scoped throttle at 120/minute.
    """

    permission_classes = [IsOrgScoped]  # noqa: RUF012
    serializer_class = AuditLogReadSerializer
    pagination_class = AuditLogCursorPagination
    filter_backends = [DjangoFilterBackend]  # noqa: RUF012
    filterset_class = AuditLogFilterSet
    throttle_scope = "audit_log_list"
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    # Required for DRF router introspection; real querysets come from get_queryset().
    queryset = AuditLog.objects.none()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return AuditLog.objects.none()
        if getattr(user, "role", None) == User.Role.STAFF_ADMIN:
            return list_audit_logs_for_staff(organisation_id=org_id, user=user)
        return list_audit_logs_for_org(organisation_id=org_id)


@login_required(login_url="/login/")
def audit_log_view(request: HttpRequest) -> HttpResponse:
    """Org Admin / Staff Admin activity log template view (Phase 21).

    Renders the audit-log page shell. The data table is hydrated client-side
    via /api/v1/audit-logs/. The actor filter dropdown is seeded with the
    distinct set of actors who have audit log entries in this organisation.
    """
    org_id = getattr(request.user, "organisation_id", None)
    actors_list: list[dict[str, object]] = []
    if org_id is not None:
        actors_qs = (
            AuditLog.objects.filter(organisation_id=org_id)
            .filter(actor__isnull=False)
            .select_related("actor")
            .values("actor_id", "actor__full_name")
            .distinct()
            .order_by("actor__full_name")
        )
        actors_list = [
            {"id": row["actor_id"], "full_name": row["actor__full_name"]}
            for row in actors_qs
        ]
    context = {
        "actors_json": actors_list,
        "user_role": getattr(request.user, "role", ""),
        "page_title": "Activity Log",
    }
    return render(request, "org-admin/audit-log.html", context)
