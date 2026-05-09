from __future__ import annotations

from typing import cast

from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpRequest
from django.shortcuts import render
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped, RequiresSessionAuth
from apps.common.viewsets import TenantScopedViewSet
from apps.regions.exceptions import RegionHasShopsError
from apps.regions.models import Region
from apps.regions.selectors.regions import list_regions
from apps.regions.serializers import (
    RegionCreateSerializer,
    RegionReadSerializer,
    RegionUpdateSerializer,
)
from apps.regions.services.regions import create_region, delete_region, update_region

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


@org_admin_required
def region_list(request):  # type: ignore[no-untyped-def]
    search = request.GET.get("search", "")
    per_page = _resolve_per_page(request.GET.get("per_page"))

    regions_qs = list_regions(organisation_id=request.user.organisation_id, search=search)
    paginator = Paginator(regions_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    regions_data = list(RegionReadSerializer(list(page_obj.object_list), many=True).data)

    return render(
        request,
        "regions/region_list.html",
        {
            "regions_json": regions_data,
            "regions_count": len(regions_data),
            "page_obj": page_obj,
            "per_page": per_page,
            "per_page_options": list(PER_PAGE_OPTIONS),
            "page_url_params": _page_url_params(request, per_page),
            "search": search,
            "page_title": "Regions",
        },
    )


class RegionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgAdmin, IsOrgScoped]  # noqa: RUF012
    queryset = Region.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return cast(list[BasePermission], super().get_permissions())

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Region]]:
        if self.action == "create":
            return RegionCreateSerializer
        if self.action == "partial_update":
            return RegionUpdateSerializer
        return RegionReadSerializer

    @extend_schema(exclude=True)
    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        region = self.perform_create(serializer)
        read_serializer = RegionReadSerializer(region)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(  # type: ignore[override]
        self, serializer: serializers.BaseSerializer[Region]
    ) -> Region:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise serializers.ValidationError({"detail": ["Organisation not found."]})
        try:
            return create_region(
                organisation=user.organisation,
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            ) from exc

    @extend_schema(exclude=True)
    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        region = self.perform_update(serializer)
        read_serializer = RegionReadSerializer(region)
        return Response(read_serializer.data)

    def perform_update(  # type: ignore[override]
        self, serializer: serializers.BaseSerializer[Region]
    ) -> Region:
        try:
            return update_region(
                region=serializer.instance,  # type: ignore[arg-type]
                **serializer.validated_data,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"region_id": ["This Region ID is already in use."]}
            ) from exc

    @extend_schema(exclude=True)
    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        region = self.get_object()
        try:
            delete_region(region=region)
        except RegionHasShopsError as exc:
            return Response({"shop_count": exc.shop_count}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
