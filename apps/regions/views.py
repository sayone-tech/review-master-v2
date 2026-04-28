from __future__ import annotations

from django.db import IntegrityError
from django.shortcuts import render
from rest_framework import mixins, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped
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


@org_admin_required
def region_list(request):  # type: ignore[no-untyped-def]
    regions_qs = list_regions(organisation_id=request.user.organisation_id)
    regions_data = list(RegionReadSerializer(regions_qs, many=True).data)
    return render(
        request,
        "regions/region_list.html",
        {
            "regions_json": regions_data,
            "regions_count": len(regions_data),
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

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Region]]:
        if self.action == "create":
            return RegionCreateSerializer
        if self.action == "partial_update":
            return RegionUpdateSerializer
        return RegionReadSerializer

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

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

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

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        region = self.get_object()
        try:
            delete_region(region=region)
        except RegionHasShopsError as exc:
            return Response({"shop_count": exc.shop_count}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
