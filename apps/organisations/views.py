from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsSuperadmin, org_admin_required
from apps.organisations.models import Organisation
from apps.organisations.selectors.organisations import (
    list_organisations as list_organisations_selector,
)
from apps.organisations.serializers import (
    OrganisationCreateSerializer,
    OrganisationDetailSerializer,
    OrganisationListSerializer,
    OrganisationUpdateSerializer,
)
from apps.organisations.services.organisations import (
    create_organisation,
    delete_organisation,
    update_organisation,
)
from apps.regions.models import Region

if TYPE_CHECKING:
    from django.db.models import QuerySet

PER_PAGE_OPTIONS: tuple[int, ...] = (10, 25, 50, 100)
DEFAULT_PER_PAGE: int = 10


def _resolve_per_page(raw: str | None) -> int:
    try:
        value = int(raw) if raw is not None else DEFAULT_PER_PAGE
    except (TypeError, ValueError):
        return DEFAULT_PER_PAGE
    return value if value in PER_PAGE_OPTIONS else DEFAULT_PER_PAGE


def _page_url_params(request: HttpRequest, per_page: int) -> str:
    params = request.GET.copy()
    params["per_page"] = str(per_page)
    params.pop("page", None)
    return params.urlencode()


@login_required
def organisation_list(request: HttpRequest) -> HttpResponse:
    user = request.user
    if not isinstance(user, User):
        return redirect("/login/")
    if user.role != User.Role.SUPERADMIN:
        return redirect("/admin/org/dashboard/")

    per_page = _resolve_per_page(request.GET.get("per_page"))
    search = request.GET.get("search", "")
    current_status = request.GET.get("status", "")
    current_type = request.GET.get("type", "")

    qs = list_organisations_selector(search=search, status=current_status, org_type=current_type)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    orgs_payload = OrganisationListSerializer(list(page_obj.object_list), many=True).data
    # Pass the list so the template can use {{ orgs_json|json_script:"org-data" }}
    # without double-encoding. json_script handles safe serialization.
    orgs_json = list(orgs_payload)

    status_options: list[tuple[str, str]] = [
        ("", "All Statuses"),
        (Organisation.Status.ACTIVE.value, "Active"),
        (Organisation.Status.DISABLED.value, "Disabled"),
    ]
    type_options: list[tuple[str, str]] = [("", "All Types")] + [
        (value, label) for value, label in Organisation.OrgType.choices
    ]

    context: dict[str, Any] = {
        "page_obj": page_obj,
        "orgs_json": orgs_json,
        "per_page": per_page,
        "per_page_options": list(PER_PAGE_OPTIONS),
        "status_options": status_options,
        "type_options": type_options,
        "page_url_params": _page_url_params(request, per_page),
        "total_count": paginator.count,
        "search": search,
        "current_status": current_status,
        "current_type": current_type,
    }
    return render(request, "organisations/list.html", context)


@login_required
def org_admin_dashboard(request: HttpRequest) -> HttpResponse:
    """Personalised Org Admin / Staff Admin dashboard.

    - SUPERADMIN → redirect to /admin/organisations/
    - ORG_ADMIN / STAFF_ADMIN with organisation → render React dashboard island
    - ORG_ADMIN without organisation → 403 (NOT redirect, per SHEL spec)
    - Anonymous → @login_required redirects to /login/?next=...
    """
    from apps.reviews.selectors.reviews import get_accessible_shop_ids
    from apps.shops.models import Shop

    user = request.user
    # assert type narrowing for mypy strict
    if not isinstance(user, User):
        return redirect("/login/")
    if user.role == User.Role.SUPERADMIN:
        return redirect("/admin/organisations/")
    if user.organisation is None or user.organisation_id is None:
        return HttpResponseForbidden("Organisation Admin role required.")

    org_id: int = user.organisation_id
    accessible_shop_ids = list(get_accessible_shop_ids(user_id=user.pk))

    shops = list(
        Shop.objects.filter(
            organisation_id=org_id,
            id__in=accessible_shop_ids,
        )
        .select_related("region")
        .values("id", "name", "region_id")
        .order_by("name")
    )
    region_ids = {s["region_id"] for s in shops if s["region_id"]}
    regions = list(Region.objects.filter(id__in=region_ids).values("id", "name").order_by("name"))
    is_single_shop = len(accessible_shop_ids) == 1

    context: dict[str, Any] = {
        "regions_json": regions,
        "shops_json": shops,
        "is_single_shop": is_single_shop,
        "is_org_admin": user.role == User.Role.ORG_ADMIN,
    }
    return render(request, "organisations/org_dashboard.html", context)


_STUB_DISPLAY: dict[str, tuple[str, str]] = {
    "regions": ("Regions", "map-pin"),
    "shops": ("Shops", "store"),
    "team": ("Team", "users"),
}


@org_admin_required
def org_stub_view(request: HttpRequest, section: str) -> HttpResponse:
    """Shared stub view for /admin/org/{regions,shops,team}/ during Phase 6.

    Phases 7, 8, 9 replace each URL's view with the real list page.
    """
    title, icon = _STUB_DISPLAY.get(section, (section.title(), "inbox"))
    return render(
        request,
        "organisations/org_stub.html",
        {
            "section": title,
            "section_slug": section,
            "section_icon": icon,
        },
    )


@org_admin_required
def team_list(request: HttpRequest) -> HttpResponse:
    """Org Admin team management page — /admin/org/team/.

    Seeds initial JSON for the React widget. Replaces Phase 6 stub.
    """
    from typing import cast as _cast

    from apps.accounts.selectors.team import get_team_stats, list_team_members
    from apps.accounts.serializers import TeamMemberReadSerializer
    from apps.regions.selectors.regions import list_regions
    from apps.regions.serializers import RegionReadSerializer
    from apps.shops.selectors.shops import list_shops
    from apps.shops.serializers import ShopReadSerializer

    user = _cast(User, request.user)  # @org_admin_required guarantees authenticated ORG_ADMIN
    org = user.organisation  # IsOrgAdmin ensures organisation is set
    if org is None:
        return HttpResponseForbidden("Organisation required.")
    per_page_options = (10, 25, 50, 100)
    default_per_page = 10
    try:
        per_page = int(request.GET.get("per_page", default_per_page))
        if per_page not in per_page_options:
            per_page = default_per_page
    except (TypeError, ValueError):
        per_page = default_per_page

    members_qs = list_team_members(organisation_id=org.pk)
    paginator = Paginator(members_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    members_data = list(TeamMemberReadSerializer(list(page_obj.object_list), many=True).data)

    params = request.GET.copy()
    params["per_page"] = str(per_page)
    params.pop("page", None)
    page_url_params = params.urlencode()

    regions_qs = list_regions(organisation_id=org.pk)
    regions_data = list(RegionReadSerializer(regions_qs, many=True).data)
    # XMOD-03 — active shops only for scope selectors
    active_shops_qs = list_shops(organisation_id=org.pk, active_only=True)
    active_shops_data = list(ShopReadSerializer(active_shops_qs, many=True).data)
    stats = get_team_stats(organisation_id=org.pk)
    return render(
        request,
        "team/team_list.html",
        {
            "initial_members_json": members_data,
            "regions_json": regions_data,
            "active_shops_json": active_shops_data,
            "stats": stats,
            "manager_count": stats["managers"],
            "current_user_id": user.pk,
            "page_obj": page_obj,
            "per_page": per_page,
            "per_page_options": list(per_page_options),
            "page_url_params": page_url_params,
            "page_title": "Team",
        },
    )


@login_required
def org_welcome(request: HttpRequest) -> HttpResponse:
    """Staff welcome stub page — /admin/org/welcome/.

    Rendered after TEAM_MEMBER activation for STAFF_ADMIN users.
    """
    return render(request, "organisations/team_welcome.html", {"page_title": "Welcome"})


class OrganisationViewSet(viewsets.ModelViewSet[Organisation]):
    permission_classes = [IsAuthenticated, IsSuperadmin]  # noqa: RUF012
    pagination_class = PageNumberPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012
    lookup_field = "pk"

    def get_queryset(self) -> QuerySet[Organisation]:
        return list_organisations_selector(
            search=self.request.query_params.get("search", ""),
            status=self.request.query_params.get("status", ""),
            org_type=self.request.query_params.get("type", ""),
        )

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Organisation]]:
        # NOTE (intentional design): create() action returns OrganisationCreateSerializer
        # for the 201 response body. This is the minimal echo-back of the 5 input fields
        # (name, org_type, email, address, number_of_stores) — the React widget does NOT
        # rely on the 201 response for full org details; it re-fetches the list after
        # successful create. If downstream plans require the full detail shape in the 201
        # body, override create() to re-serialize with OrganisationDetailSerializer after
        # perform_create. For now the minimal response is acceptable per 03-CONTEXT.md.
        if self.action == "list":
            return OrganisationListSerializer
        if self.action == "create":
            return OrganisationCreateSerializer
        if self.action == "partial_update":
            return OrganisationUpdateSerializer
        return OrganisationDetailSerializer

    def perform_create(self, serializer: serializers.BaseSerializer[Organisation]) -> None:
        if not isinstance(self.request.user, User):
            raise TypeError("Authenticated User required")
        try:
            org, _token = create_organisation(
                created_by=self.request.user,
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"email": ["An organisation with this email already exists."]}
            ) from exc
        serializer.instance = org

    def perform_update(self, serializer: serializers.BaseSerializer[Organisation]) -> None:
        if serializer.instance is None:
            raise ValueError("serializer.instance must be set before update")
        update_organisation(
            organisation=serializer.instance,
            **serializer.validated_data,
        )

    def perform_destroy(self, instance: Organisation) -> None:
        delete_organisation(organisation=instance)

    @action(
        detail=True, methods=["post"], url_path="resend-invitation", url_name="resend-invitation"
    )
    def resend_invitation(self, request: HttpRequest, pk: int | None = None) -> Response:
        """POST /api/v1/organisations/<pk>/resend-invitation/ — INVT-01.

        IsSuperadmin permission applied via get_object() -> permission_classes.
        """
        from apps.organisations.services.organisations import (
            resend_invitation as resend_invitation_service,
        )

        org = self.get_object()
        if not isinstance(request.user, User):
            raise TypeError("Authenticated User required")
        resend_invitation_service(organisation=org, resent_by=request.user)
        return Response({"detail": "Invitation resent."}, status=200)
