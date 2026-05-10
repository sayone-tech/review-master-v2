from __future__ import annotations

import contextlib
import json
import logging
import secrets
from typing import Any

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped, RequiresSessionAuth
from apps.common.viewsets import TenantScopedViewSet
from apps.integrations.google.exceptions import (
    GoogleAuthError,
    GoogleUnreachableError,
)
from apps.integrations.google.oauth import (
    build_auth_url,
    exchange_code_for_token,
    list_business_locations,
)
from apps.regions.selectors.regions import list_regions
from apps.regions.serializers import RegionReadSerializer
from apps.reviews.tasks import initial_backfill_task
from apps.shops.exceptions import PlaceIdLockedError, ShopAtLimitError
from apps.shops.models import ReviewTarget, Shop
from apps.shops.selectors.shops import get_allocation_status, get_has_regions, list_shops
from apps.shops.selectors.targets import list_targets_for_shop
from apps.shops.serializers import (
    ReviewTargetCreateSerializer,
    ReviewTargetReadSerializer,
    ReviewTargetUpdateSerializer,
    ShopCreateSerializer,
    ShopReadSerializer,
    ShopUpdateSerializer,
)
from apps.shops.services.shops import (
    activate_shop,
    create_shop,
    deactivate_shop,
    reconnect_oauth,
    update_shop,
)
from apps.shops.services.targets import (
    create_target,
    delete_target,
    update_target,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template view — /admin/org/shops/
# ---------------------------------------------------------------------------


_SHOP_PER_PAGE_OPTIONS: tuple[int, ...] = (10, 25, 50, 100)
_SHOP_DEFAULT_PER_PAGE: int = 10


def _shop_resolve_per_page(raw: str | None) -> int:
    try:
        value = int(raw) if raw is not None else _SHOP_DEFAULT_PER_PAGE
    except (TypeError, ValueError):
        return _SHOP_DEFAULT_PER_PAGE
    return value if value in _SHOP_PER_PAGE_OPTIONS else _SHOP_DEFAULT_PER_PAGE


def _shop_page_url_params(request: HttpRequest, per_page: int) -> str:
    params = request.GET.copy()
    params["per_page"] = str(per_page)
    params.pop("page", None)
    return params.urlencode()


@org_admin_required
def shop_list(request):  # type: ignore[no-untyped-def]
    org = request.user.organisation
    per_page = _shop_resolve_per_page(request.GET.get("per_page"))
    qs = list_shops(organisation_id=org.pk)
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    shops_data = list(ShopReadSerializer(list(page_obj.object_list), many=True).data)
    regions_qs = list_regions(organisation_id=org.pk)
    regions_data = list(RegionReadSerializer(regions_qs, many=True).data)
    return render(
        request,
        "shops/shop_list.html",
        {
            "shops_json": shops_data,
            "shops_count": len(shops_data),
            "allocation": get_allocation_status(organisation=org),
            "has_regions": get_has_regions(organisation_id=org.pk),
            "regions_json": regions_data,
            "page_obj": page_obj,
            "per_page": per_page,
            "per_page_options": list(_SHOP_PER_PAGE_OPTIONS),
            "page_url_params": _shop_page_url_params(request, per_page),
            "page_title": "Shops",
        },
    )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class ShopsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ---------------------------------------------------------------------------
# DRF ViewSet
# ---------------------------------------------------------------------------


class ShopViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    TenantScopedViewSet,
):
    permission_classes = [IsOrgAdmin, IsOrgScoped]  # noqa: RUF012
    queryset = Shop.objects.select_related("region").all()
    http_method_names = ["get", "post", "patch", "head", "options"]  # noqa: RUF012
    pagination_class = ShopsPagination

    def get_permissions(self) -> list[BasePermission]:
        if self.action in (
            "create",
            "update",
            "partial_update",
            "activate",
            "deactivate",
            "reconnect",
        ):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        # Read actions (list, retrieve) are open to both ORG_ADMIN and STAFF_ADMIN.
        return [IsOrgScoped()]

    def get_serializer_class(self) -> type[drf_serializers.BaseSerializer[Any]]:
        if self.action == "create":
            return ShopCreateSerializer
        if self.action in ("partial_update", "update"):
            return ShopUpdateSerializer
        return ShopReadSerializer

    def get_serializer_context(self) -> dict[str, Any]:
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    # ------------------------------------------------------------------
    # List — injects allocation_status and has_regions into envelope
    # ------------------------------------------------------------------

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user
        if not isinstance(user, User) or user.organisation is None:
            raise drf_serializers.ValidationError({"detail": ["Organisation not found."]})
        org = user.organisation
        qs = list_shops(
            organisation_id=org.pk,
            search=request.query_params.get("search", ""),
            status=request.query_params.get("status", ""),
            region_id=int(request.query_params["region"])
            if request.query_params.get("region")
            else None,
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
        else:
            response = Response({"results": serializer.data})
        response.data["allocation_status"] = get_allocation_status(organisation=org)
        response.data["has_regions"] = get_has_regions(organisation_id=org.pk)
        return response

    # ------------------------------------------------------------------
    # Create — returns ShopReadSerializer in 201 (Phase 7 pattern)
    # ------------------------------------------------------------------

    @extend_schema(exclude=True)
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = self.perform_create(serializer)
        read_serializer = ShopReadSerializer(shop)
        headers = self.get_success_headers(read_serializer.data)
        response_data = dict(read_serializer.data)
        if shop.connection_method == Shop.ConnectionMethod.GOOGLE_OAUTH:
            response_data["open_progress_shop_id"] = shop.pk
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(  # type: ignore[override]
        self, serializer: drf_serializers.BaseSerializer[Any]
    ) -> Shop:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise drf_serializers.ValidationError({"detail": ["Organisation not found."]})
        data = dict(serializer.validated_data)
        region = data.pop("region", None)

        # OAuth state -> refresh_token resolution from session (SHOP-13).
        # The frontend (Plan 08-05) sends the OAuth `state` value in the
        # `google_refresh_token` field (NOT the actual refresh token).
        # Resolve it to the actual token from session here.
        if data.get("connection_method") == Shop.ConnectionMethod.GOOGLE_OAUTH:
            state_value = data.get("google_refresh_token", "")
            token = self.request.session.get(f"oauth_token:{state_value}") if state_value else None
            if not token:
                raise drf_serializers.ValidationError(
                    {"non_field_errors": ["OAuth session expired. Please reconnect."]}
                )
            data["google_refresh_token"] = token
            # Resolve google_account_name / google_location_name from the
            # session-stored listings (set during OAuth callback). The frontend
            # only sends place_id; these GBP resource names come from the server.
            listings: list[dict[str, str]] = self.request.session.get(
                f"oauth_listings:{state_value}", []
            )
            place_id = data.get("place_id", "")
            matched = next((lst for lst in listings if lst.get("place_id") == place_id), None)
            if not matched:
                raise drf_serializers.ValidationError(
                    {"non_field_errors": ["Location not found in OAuth session. Please reconnect."]}
                )
            data["google_account_name"] = matched["account_name"]
            data["google_location_name"] = matched["location_name"]
            # Single-use: consume the session-stored token after successful lookup.
            with contextlib.suppress(KeyError):
                del self.request.session[f"oauth_token:{state_value}"]

        try:
            shop = create_shop(organisation=user.organisation, region=region, **data)
        except ShopAtLimitError:
            raise drf_serializers.ValidationError(
                {"non_field_errors": ["Shop allocation limit reached."]}
            ) from None
        # Phase 11 — dispatch initial backfill if Google-connected.
        if shop.connection_method == Shop.ConnectionMethod.GOOGLE_OAUTH:
            try:
                initial_backfill_task.delay(shop_id=shop.pk)
            except Exception:
                logger.warning(
                    "Failed to dispatch initial_backfill_task for shop=%s; will retry on next Beat tick",
                    shop.pk,
                )
        return shop

    # ------------------------------------------------------------------
    # Update — returns ShopReadSerializer in 200
    # ------------------------------------------------------------------

    @extend_schema(exclude=True)
    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        shop = self.perform_update(serializer)
        read_serializer = ShopReadSerializer(shop)
        return Response(read_serializer.data)

    def perform_update(  # type: ignore[override]
        self, serializer: drf_serializers.BaseSerializer[Any]
    ) -> Shop:
        try:
            return update_shop(shop=serializer.instance, **serializer.validated_data)  # type: ignore[arg-type]
        except PlaceIdLockedError as exc:
            raise drf_serializers.ValidationError(
                {"non_field_errors": ["This field cannot be modified after creation."]}
            ) from exc

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @extend_schema(exclude=True)
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        activate_shop(shop=shop)
        return Response(ShopReadSerializer(shop).data)

    @extend_schema(exclude=True)
    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        deactivate_shop(shop=shop)
        return Response(ShopReadSerializer(shop).data)

    @extend_schema(exclude=True)
    @action(detail=True, methods=["post"], url_path="reconnect")
    def reconnect(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        state_value = request.data.get("state", "")
        token = request.session.get(f"oauth_token:{state_value}")
        if not token:
            return Response(
                {"detail": "OAuth token not found in session."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Resolve google_account_name / google_location_name from session listings.
        # Match by the shop's existing place_id (reconnect keeps the same location).
        listings: list[dict[str, str]] = request.session.get(f"oauth_listings:{state_value}", [])
        matched = next((lst for lst in listings if lst.get("place_id") == shop.place_id), None)
        reconnect_oauth(shop=shop, new_refresh_token=token)
        if matched:
            update_shop(
                shop=shop,
                google_account_name=matched["account_name"],
                google_location_name=matched["location_name"],
            )
        # Clean up session key after use (single-use).
        with contextlib.suppress(KeyError):
            del request.session[f"oauth_token:{state_value}"]
        # Phase 11 — dispatch initial backfill and signal frontend to open ProgressModal.
        try:
            initial_backfill_task.delay(shop_id=shop.pk)
        except Exception:
            logger.warning(
                "Failed to dispatch initial_backfill_task on reconnect for shop=%s", shop.pk
            )
        data = dict(ShopReadSerializer(shop).data)
        data["open_progress_shop_id"] = shop.pk
        return Response(data)

    @action(
        detail=False,
        methods=["get"],
        url_path="syncing",
        permission_classes=[IsOrgScoped],  # Staff Admins may also check sync progress
    )
    def syncing(self, request: Request) -> Response:
        """Return shops with active progress snapshots (for topbar indicator)."""
        from apps.reviews.selectors.reviews import get_accessible_shop_ids

        user = request.user
        if not isinstance(user, User) or user.organisation is None:
            return Response({"count": 0, "shops": []})

        qs = Shop.objects.filter(organisation_id=user.organisation_id).only("id", "name")  # type: ignore[misc]
        if user.role == User.Role.STAFF_ADMIN:
            accessible = get_accessible_shop_ids(user_id=user.pk)
            qs = qs.filter(id__in=accessible)
        try:
            r = get_redis_connection("default")
        except Exception:
            return Response({"count": 0, "shops": []})

        syncing_shops = []
        for shop in qs:
            try:
                raw = r.get(f"sync:progress:{shop.pk}")
                if raw:
                    snapshot = json.loads(raw)
                    if snapshot.get("status") in ("fetching", "enriching"):
                        syncing_shops.append({"shop_id": shop.pk, "shop_name": shop.name})
            except Exception:  # noqa: S112  # nosec B112
                continue
        return Response({"count": len(syncing_shops), "shops": syncing_shops})

    @action(detail=False, methods=["get"], url_path="oauth_result")
    def oauth_result(self, request: Request) -> Response:
        # State resolution: query param OR session fallback (Plan 08-05 polling fires
        # without knowing the state; backend recovers it from session.)
        state_value = request.query_params.get("state") or request.session.get("oauth_state", "")
        if not state_value:
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            r = get_redis_connection("default")
            data = r.get(f"oauth:result:{state_value}")
        except Exception:
            logger.warning("Redis unavailable in oauth_result; returning 204")
            return Response(status=status.HTTP_204_NO_CONTENT)
        if not data:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(json.loads(data))


# ---------------------------------------------------------------------------
# OAuth Views (plain Django views — NOT DRF)
# ---------------------------------------------------------------------------


class GoogleOAuthStartView(View):
    """Initiate the Google OAuth 2.0 flow for a store connection.

    Generates a CSRF-like state token, stores in session, then redirects to
    Google's authorization endpoint. Sets Cross-Origin-Opener-Policy so the
    popup can communicate with the opener via postMessage.
    """

    def get(self, request: Any) -> Any:
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state
        auth_url = build_auth_url(state=state)
        response = HttpResponseRedirect(auth_url)
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response


class GoogleOAuthCallbackView(View):
    """Handle the Google OAuth 2.0 callback.

    Exchanges the authorization code, lists business locations, then renders
    a popup template that postMessages the result back to the opener window.
    Sets Cross-Origin-Opener-Policy on every response.
    """

    def _render_error(self, request: Any, code: str, state: str = "") -> Any:
        # Write error to Redis so the COOP close-watcher fallback can detect
        # the error type instead of falling through to generic "closed".
        if state:
            try:
                r = get_redis_connection("default")
                r.setex(
                    f"oauth:result:{state}",
                    30,
                    json.dumps({"type": "oauth_error", "state": state, "code": code}),
                )
            except Exception:  # noqa: S110  # nosec B110
                pass
        response = render(
            request,
            "shops/oauth/callback.html",
            {"oauth_error_code": code, "state": state, "listings": []},
        )
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response

    def get(self, request: Any) -> Any:
        state = request.GET.get("state", "")
        session_state = request.session.get("oauth_state", "")
        if not state or state != session_state:
            return self._render_error(request, "auth_error")

        if request.GET.get("error"):
            error = request.GET.get("error")
            code = "denied" if error == "access_denied" else "auth_error"
            return self._render_error(request, code, state)

        code_param = request.GET.get("code", "")
        if not code_param:
            return self._render_error(request, "denied", state)

        try:
            tokens = exchange_code_for_token(code=code_param)
        except (GoogleAuthError, GoogleUnreachableError):
            return self._render_error(request, "auth_error", state)

        try:
            listings = list_business_locations(refresh_token=tokens["refresh_token"])
        except (GoogleAuthError, GoogleUnreachableError):
            return self._render_error(request, "auth_error", state)

        if not listings:
            return self._render_error(request, "no_listings", state)

        # Persist refresh_token to session keyed by state for later POST from modal.
        request.session[f"oauth_token:{state}"] = tokens["refresh_token"]
        request.session[f"oauth_listings:{state}"] = listings

        # Write Redis polling fallback (30s TTL) for Plan 08-05 oauth_result endpoint.
        # Best-effort: postMessage is the primary path; Redis failure is non-fatal.
        try:
            r = get_redis_connection("default")
            r.setex(
                f"oauth:result:{state}",
                30,
                json.dumps(
                    {
                        "type": "oauth_listings",
                        "state": state,
                        "listings": listings,
                    }
                ),
            )
        except Exception:
            logger.warning("Redis write failed for oauth:result:%s — non-fatal", state)

        response = render(
            request,
            "shops/oauth/callback.html",
            {"listings": listings, "listings_json": json.dumps(listings), "state": state},
        )
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response


# ---------------------------------------------------------------------------
# ReviewTarget ViewSet — nested under /api/v1/shops/{shop_pk}/targets/
# ---------------------------------------------------------------------------


class ReviewTargetViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    queryset = ReviewTarget.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "partial_update", "update", "destroy"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return [IsOrgScoped()]

    def _get_shop_pk(self) -> int:
        return int(self.kwargs["shop_pk"])

    def _get_org_id(self) -> int:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise drf_serializers.ValidationError({"detail": ["Organisation not found."]})
        return int(user.organisation_id)  # type: ignore[arg-type]

    def _verify_shop_org(self, shop_pk: int, org_id: int) -> None:
        """Raise 403 if shop does not belong to the requesting user's organisation."""
        from rest_framework.exceptions import PermissionDenied

        if not Shop.objects.filter(pk=shop_pk, organisation_id=org_id).exists():
            raise PermissionDenied()

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        org_id = self._get_org_id()
        shop_pk = self._get_shop_pk()
        self._verify_shop_org(shop_pk, org_id)
        results = list_targets_for_shop(
            shop_id=shop_pk,
            org_id=org_id,
        )
        return Response(ReviewTargetReadSerializer(results, many=True).data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReviewTargetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not isinstance(user, User):
            raise drf_serializers.ValidationError({"detail": ["Authentication required."]})
        try:
            target = create_target(
                shop_id=self._get_shop_pk(),
                org_id=self._get_org_id(),
                period_type=serializer.validated_data["period_type"],
                period_start=serializer.validated_data["period_start"],
                target_count=serializer.validated_data["target_count"],
                created_by=user,
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Shop not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            raise drf_serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        results = list_targets_for_shop(
            shop_id=self._get_shop_pk(),
            org_id=self._get_org_id(),
        )
        row = next((r for r in results if r["id"] == target.pk), None)
        return Response(ReviewTargetReadSerializer(row).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReviewTargetUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            update_target(
                target_id=int(kwargs["pk"]),
                org_id=self._get_org_id(),
                target_count=serializer.validated_data["target_count"],
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            raise drf_serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        results = list_targets_for_shop(
            shop_id=self._get_shop_pk(),
            org_id=self._get_org_id(),
        )
        row = next((r for r in results if r["id"] == int(kwargs["pk"])), None)
        return Response(ReviewTargetReadSerializer(row).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            delete_target(
                target_id=int(kwargs["pk"]),
                org_id=self._get_org_id(),
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
