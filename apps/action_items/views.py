"""Phase 13 plan 04 — ActionItem REST API + template page view."""

from __future__ import annotations

import json
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response

from apps.action_items.filters import ActionItemFilterSet
from apps.action_items.models import ActionItem
from apps.action_items.permissions import BrandScopeGuard
from apps.action_items.selectors.items import list_action_items
from apps.action_items.serializers import (
    ActionItemCreateSerializer,
    ActionItemListSerializer,
    ActionItemNoteCreateSerializer,
    ActionItemNoteSerializer,
    ActionItemReadSerializer,
    ActionItemUpdateSerializer,
    StatusTransitionSerializer,
)
from apps.action_items.services.lifecycle import (
    add_note,
    assign_action_item,
    create_action_item,
    transition_status,
)
from apps.common.pagination import DefaultPageNumberPagination
from apps.common.permissions import IsOrgScoped


class ActionItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[Any],
):
    """ActionItem CRUD + custom transition-status / add-note actions.

    Three-layer Staff scope:
      - Layer 1 (selector): list_action_items filters Staff to SHOP-scope only.
      - Layer 2 (permission): BrandScopeGuard returns 403 for direct-id access
        to BRAND items by Staff.
      - Layer 3 (UI): hide brand controls in plan 13-06/07.
    """

    permission_classes = [IsOrgScoped, BrandScopeGuard]  # noqa: RUF012
    pagination_class = DefaultPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]  # noqa: RUF012
    filterset_class = ActionItemFilterSet
    ordering_fields = ["created_at", "due_date", "status", "priority"]  # noqa: RUF012
    ordering = ["-created_at"]  # noqa: RUF012
    queryset = ActionItem.objects.none()

    def get_serializer_class(self):  # type: ignore[no-untyped-def]
        if self.action == "list":
            return ActionItemListSerializer
        if self.action == "create":
            return ActionItemCreateSerializer
        if self.action in ("update", "partial_update"):
            return ActionItemUpdateSerializer
        return ActionItemReadSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user = self.request.user
        org_id = getattr(user, "organisation_id", None)
        if org_id is None:
            return ActionItem.objects.none()
        qs = list_action_items(organisation_id=org_id, user=user)  # type: ignore[arg-type]
        if self.action == "retrieve":
            qs = qs.prefetch_related("notes__author")
        return qs

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shop = data.get("shop")
        assignee = data.get("assignee")
        item = create_action_item(
            organisation_id=request.user.organisation_id,  # type: ignore[union-attr,arg-type]
            title=data["title"],
            scope=data["scope"],
            priority=data.get("priority", ActionItem.Priority.MEDIUM),
            source=ActionItem.Source.MANUAL,
            actor=request.user,  # type: ignore[arg-type]
            shop_id=shop.pk if shop else None,
            assignee_id=assignee.pk if assignee else None,
            due_date=data.get("due_date"),
            initial_note=data.get("initial_note") or None,
        )
        return Response(ActionItemReadSerializer(item).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer: Any) -> None:
        item = serializer.instance
        new_assignee = serializer.validated_data.get("assignee", "__unset__")
        serializer.save()
        if new_assignee != "__unset__":
            new_assignee_id = new_assignee.pk if new_assignee else None
            if new_assignee_id != item.assignee_id:
                assign_action_item(
                    action_item=item,
                    assignee_id=new_assignee_id,
                    actor=self.request.user,  # type: ignore[arg-type]
                )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance.refresh_from_db()
        return Response(ActionItemReadSerializer(instance).data)

    @action(detail=True, methods=["post"], url_path="transition-status")
    def transition_status_action(self, request: Request, pk: int | None = None) -> Response:
        item = self.get_object()
        s = StatusTransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        item = transition_status(
            action_item=item,
            new_status=s.validated_data["status"],
            actor=request.user,  # type: ignore[arg-type]
        )
        return Response(ActionItemReadSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="add-note")
    def add_note_action(self, request: Request, pk: int | None = None) -> Response:
        item = self.get_object()
        s = ActionItemNoteCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        note = add_note(
            action_item=item,
            author=request.user,  # type: ignore[arg-type]
            body=s.validated_data["body"],
        )
        return Response(ActionItemNoteSerializer(note).data, status=status.HTTP_201_CREATED)


@login_required(login_url="/login/")
def action_item_list_view(request: HttpRequest) -> HttpResponse:
    """Template view that renders the React mount point for the action items page."""
    user = request.user
    org_id = getattr(user, "organisation_id", None)

    shops_data: list[Any] = []
    team_data: list[Any] = []
    if org_id is not None:
        from apps.shops.models import Shop

        shops_qs = Shop.objects.filter(organisation_id=org_id, is_active=True)
        if getattr(user, "role", "") == "STAFF_ADMIN" and user.pk is not None:
            from apps.reviews.selectors.reviews import get_accessible_shop_ids

            shops_qs = shops_qs.filter(id__in=get_accessible_shop_ids(user_id=user.pk))
        shops_data = list(shops_qs.values("id", "name").order_by("name"))

        from apps.accounts.models import User as UserModel

        team_data = list(
            UserModel.objects.filter(
                organisation_id=org_id,
                role__in=[UserModel.Role.ORG_ADMIN, UserModel.Role.STAFF_ADMIN],
                is_active=True,
            )
            .values("id", "full_name")
            .order_by("full_name")
        )

    return render(
        request,
        "action_items/action_item_list.html",
        {
            "page_title": "Action Items",
            "user_role": getattr(user, "role", ""),
            "user_id": user.pk,
            "shops_json": json.dumps(shops_data),
            "team_members_json": json.dumps(team_data),
        },
    )
