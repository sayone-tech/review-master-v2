from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.integrations.google.places import validate_place_id
from apps.organisations.models import Organisation
from apps.regions.models import Region
from apps.shops.exceptions import PlaceIdLockedError, ShopAtLimitError
from apps.shops.models import Shop, ShopAuditLog

_LOCKED_FIELDS = {"connection_method", "place_id"}


@transaction.atomic
def create_shop(
    *,
    organisation: Organisation,
    region: Region | None,
    name: str,
    connection_method: str,
    place_id: str = "",
    google_refresh_token: str = "",
    api_key: str = "",
    phone: str = "",
    street_address: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
    connection_status: str | None = None,
) -> Shop:
    # Allocation lock — XMOD-04
    org = Organisation.objects.select_for_update().get(pk=organisation.pk)
    current_count = Shop.objects.filter(organisation=org).count()
    if current_count >= org.number_of_stores:
        raise ShopAtLimitError()

    # SHOP-10: manual flow validates Place ID + API key BEFORE write
    if connection_method == Shop.ConnectionMethod.MANUAL and place_id and api_key:
        validate_place_id(place_id=place_id, api_key=api_key)
        # PlaceIDNotFoundError / APIKeyInvalidError / GoogleUnreachableError
        # propagate for the caller (viewset) to convert into field/non-field errors.

    if connection_status is None:
        if (
            connection_method == Shop.ConnectionMethod.GOOGLE_OAUTH
            or connection_method == Shop.ConnectionMethod.MANUAL
        ):
            connection_status = Shop.ConnectionStatus.CONNECTED
        else:
            connection_status = Shop.ConnectionStatus.NOT_CONNECTED

    return Shop.objects.create(
        organisation=org,
        region=region,
        name=name,
        connection_method=connection_method,
        connection_status=connection_status,
        place_id=place_id,
        google_refresh_token=google_refresh_token or None,
        api_key=api_key or None,
        phone=phone,
        street_address=street_address,
        city=city,
        state=state,
        zip_code=zip_code,
    )


@transaction.atomic
def update_shop(*, shop: Shop, **changes: Any) -> Shop:
    locked = _LOCKED_FIELDS & set(changes.keys())
    if locked:
        raise PlaceIdLockedError(f"Locked fields cannot be updated: {sorted(locked)}")
    changed: list[str] = []
    for key, value in changes.items():
        if getattr(shop, key, None) != value:
            setattr(shop, key, value)
            changed.append(key)
    if changed:
        changed.append("updated_at")
        shop.save(update_fields=changed)
    return shop


@transaction.atomic
def activate_shop(*, shop: Shop) -> Shop:
    if not shop.is_active:
        shop.is_active = True
        shop.save(update_fields=["is_active", "updated_at"])
    return shop


@transaction.atomic
def deactivate_shop(*, shop: Shop) -> Shop:
    if shop.is_active:
        shop.is_active = False
        shop.save(update_fields=["is_active", "updated_at"])
    return shop


@transaction.atomic
def reveal_api_key(*, shop: Shop, actor: Any) -> str:
    ShopAuditLog.objects.create(
        shop=shop,
        actor=actor,
        action=ShopAuditLog.Action.API_KEY_REVEALED,
    )
    return shop.api_key or ""


@transaction.atomic
def rotate_api_key(*, shop: Shop, actor: Any, new_api_key: str) -> Shop:
    if shop.connection_method != Shop.ConnectionMethod.MANUAL:
        raise ValueError("Shop is not on manual connection method.")
    # Validate BEFORE replacing — propagates GoogleUnreachableError, APIKeyInvalidError
    validate_place_id(place_id=shop.place_id, api_key=new_api_key)
    shop.api_key = new_api_key
    shop.save(update_fields=["api_key", "updated_at"])
    ShopAuditLog.objects.create(
        shop=shop,
        actor=actor,
        action=ShopAuditLog.Action.API_KEY_ROTATED,
    )
    return shop


@transaction.atomic
def reconnect_oauth(*, shop: Shop, new_refresh_token: str) -> Shop:
    shop.google_refresh_token = new_refresh_token
    shop.connection_status = Shop.ConnectionStatus.CONNECTED
    shop.save(
        update_fields=["google_refresh_token", "connection_status", "updated_at"],
    )
    return shop
