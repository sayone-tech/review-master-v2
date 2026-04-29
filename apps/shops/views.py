from __future__ import annotations

import contextlib
import json
import logging
import secrets
from typing import Any

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection  # type: ignore[import-untyped]
from rest_framework import mixins, status
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet
from apps.integrations.google.exceptions import (
    APIKeyInvalidError,
    GoogleAuthError,
    GoogleUnreachableError,
    PlaceIDNotFoundError,
)
from apps.integrations.google.oauth import (
    build_auth_url,
    exchange_code_for_token,
    list_business_locations,
)
from apps.shops.exceptions import PlaceIdLockedError, ShopAtLimitError
from apps.shops.models import Shop
from apps.shops.selectors.shops import get_allocation_status, get_has_regions, list_shops
from apps.shops.serializers import (
    RotateKeySerializer,
    ShopCreateSerializer,
    ShopReadSerializer,
    ShopUpdateSerializer,
)
from apps.shops.services.shops import (
    activate_shop,
    create_shop,
    deactivate_shop,
    reconnect_oauth,
    reveal_api_key,
    rotate_api_key,
    update_shop,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template view — /admin/org/shops/
# ---------------------------------------------------------------------------


@org_admin_required
def shop_list(request):  # type: ignore[no-untyped-def]
    org = request.user.organisation
    qs = list_shops(organisation_id=org.pk)[:10]  # SHOP-06: default page size 10
    shops_data = list(ShopReadSerializer(qs, many=True).data)
    return render(
        request,
        "shops/shop_list.html",
        {
            "shops_json": shops_data,
            "shops_count": Shop.objects.filter(organisation=org).count(),
            "allocation": get_allocation_status(organisation=org),
            "has_regions": get_has_regions(organisation_id=org.pk),
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

    def get_serializer_class(self) -> type[drf_serializers.BaseSerializer[Any]]:
        if self.action == "create":
            return ShopCreateSerializer
        if self.action in ("partial_update", "update"):
            return ShopUpdateSerializer
        if self.action == "rotate_key":
            return RotateKeySerializer
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

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = self.perform_create(serializer)
        read_serializer = ShopReadSerializer(shop)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

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
            # Single-use: consume the session-stored token after successful lookup.
            with contextlib.suppress(KeyError):
                del self.request.session[f"oauth_token:{state_value}"]

        try:
            return create_shop(organisation=user.organisation, region=region, **data)
        except ShopAtLimitError:
            raise drf_serializers.ValidationError(
                {"non_field_errors": ["Shop allocation limit reached."]}
            ) from None
        except (PlaceIDNotFoundError, APIKeyInvalidError, GoogleUnreachableError) as exc:
            raise self._map_google_error_to_drf(exc) from exc

    # ------------------------------------------------------------------
    # Update — returns ShopReadSerializer in 200
    # ------------------------------------------------------------------

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

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
    # Helper — maps Google API errors to DRF ValidationError
    # ------------------------------------------------------------------

    def _map_google_error_to_drf(self, exc: Exception) -> drf_serializers.ValidationError:
        if isinstance(exc, PlaceIDNotFoundError):
            return drf_serializers.ValidationError({"place_id": ["This Place ID was not found."]})
        if isinstance(exc, APIKeyInvalidError):
            return drf_serializers.ValidationError({"api_key": ["This API key is not valid."]})
        if isinstance(exc, GoogleUnreachableError):
            return drf_serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Could not reach Google to verify this API key. Please try again."
                    ]
                }
            )
        raise exc

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        activate_shop(shop=shop)
        return Response(ShopReadSerializer(shop).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        deactivate_shop(shop=shop)
        return Response(ShopReadSerializer(shop).data)

    @action(detail=True, methods=["post"], url_path="reveal_key")
    def reveal_key(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        if shop.connection_method != Shop.ConnectionMethod.MANUAL:
            return Response(
                {"detail": "Reveal key is only valid for manual-connection shops."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = reveal_api_key(shop=shop, actor=request.user)
        return Response({"api_key": key})

    @action(detail=True, methods=["post"], url_path="rotate_key")
    def rotate_key(self, request: Request, pk: int | None = None) -> Response:
        shop = self.get_object()
        ser = RotateKeySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            rotate_api_key(
                shop=shop,
                actor=request.user,
                new_api_key=ser.validated_data["new_api_key"],
            )
        except (PlaceIDNotFoundError, APIKeyInvalidError, GoogleUnreachableError) as exc:
            raise self._map_google_error_to_drf(exc) from exc
        return Response(ShopReadSerializer(shop).data)

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
        reconnect_oauth(shop=shop, new_refresh_token=token)
        # Clean up session key after use (single-use).
        with contextlib.suppress(KeyError):
            del request.session[f"oauth_token:{state_value}"]
        return Response(ShopReadSerializer(shop).data)

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
                        "type": "oauth_success",
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
            {"listings": listings, "state": state},
        )
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response

    def post(self, request: Any) -> Any:
        state = request.POST.get("state", "") or request.GET.get("state", "")
        idx_str = request.POST.get("listing_index", "")
        try:
            idx = int(idx_str)
        except (TypeError, ValueError):
            return self._render_error(request, "auth_error", state)

        listings = request.session.get(f"oauth_listings:{state}", [])
        if not listings or idx >= len(listings):
            return self._render_error(request, "auth_error", state)

        selected = [listings[idx]]
        response = render(
            request,
            "shops/oauth/callback.html",
            {"listings": selected, "state": state},
        )
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response
