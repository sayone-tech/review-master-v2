from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import render
from rest_framework import mixins, serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.reply_templates.models import ReplyTemplate
from apps.reply_templates.selectors.templates import list_templates
from apps.reply_templates.serializers import (
    ReplyTemplateCreateSerializer,
    ReplyTemplateReadSerializer,
    ReplyTemplateUpdateSerializer,
)
from apps.reply_templates.services.templates import (
    create_template,
    delete_template,
    update_template,
)

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
def template_list(request):  # type: ignore[no-untyped-def]
    search = request.GET.get("search", "")
    per_page = _resolve_per_page(request.GET.get("per_page"))

    templates_qs = list_templates(organisation_id=request.user.organisation_id, search=search)
    paginator = Paginator(templates_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    templates_data = list(ReplyTemplateReadSerializer(list(page_obj.object_list), many=True).data)

    return render(
        request,
        "reply_templates/template_list.html",
        {
            "templates_json": templates_data,
            "templates_count": len(templates_data),
            "page_obj": page_obj,
            "per_page": per_page,
            "per_page_options": list(PER_PAGE_OPTIONS),
            "page_url_params": _page_url_params(request, per_page),
            "search": search,
            "page_title": "Reply Templates",
        },
    )


class ReplyTemplateViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    queryset = ReplyTemplate.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "partial_update", "update", "destroy"):
            return [IsOrgAdmin(), IsOrgScoped()]
        # list — all org users (staff + org admin) can read templates for the picker
        return [IsOrgScoped()]

    def get_serializer_class(self) -> type[serializers.BaseSerializer[ReplyTemplate]]:
        if self.action == "create":
            return ReplyTemplateCreateSerializer
        if self.action == "partial_update":
            return ReplyTemplateUpdateSerializer
        return ReplyTemplateReadSerializer

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = self.perform_create(serializer)
        read_serializer = ReplyTemplateReadSerializer(template)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(  # type: ignore[override]
        self, serializer: serializers.BaseSerializer[ReplyTemplate]
    ) -> ReplyTemplate:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise serializers.ValidationError({"detail": ["Organisation not found."]})
        return create_template(
            organisation=user.organisation,
            **serializer.validated_data,
        )

    def partial_update(self, request: Request, *args: object, **kwargs: object) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        template = self.perform_update(serializer)
        read_serializer = ReplyTemplateReadSerializer(template)
        return Response(read_serializer.data)

    def perform_update(  # type: ignore[override]
        self, serializer: serializers.BaseSerializer[ReplyTemplate]
    ) -> ReplyTemplate:
        return update_template(
            template=serializer.instance,  # type: ignore[arg-type]
            **serializer.validated_data,
        )

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        template = self.get_object()
        delete_template(template=template)
        return Response(status=status.HTTP_204_NO_CONTENT)
