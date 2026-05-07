"""Tests for apps.dashboard.filters."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.dashboard.filters import (
    DashboardFilterParams,
    validate_filter_params,
)

pytestmark = pytest.mark.django_db


def _make_request(query: dict) -> MagicMock:
    req = MagicMock()
    req.query_params = query
    req.GET = query
    return req


def test_validate_out_of_scope_shop(org_admin_with_shops):
    """FILT-08: shop_id not in user's accessible_shop_ids → 403."""
    user = org_admin_with_shops["user"]
    org_id = org_admin_with_shops["org"].id
    # Use a shop_id that does not belong to the org.
    out_of_scope_shop_id = 99999
    req = _make_request({"store": str(out_of_scope_shop_id)})
    with pytest.raises(PermissionDenied):
        validate_filter_params(request=req, user=user, org_id=org_id)


def test_validate_range_too_long(org_admin_with_shops):
    """FILT-09: custom range > 365 days → 400."""
    user = org_admin_with_shops["user"]
    org_id = org_admin_with_shops["org"].id
    today = date.today()
    req = _make_request(
        {
            "range": "custom",
            "from": (today - timedelta(days=400)).isoformat(),
            "to": today.isoformat(),
        }
    )
    with pytest.raises(ValidationError):
        validate_filter_params(request=req, user=user, org_id=org_id)


def test_validate_from_after_to(org_admin_with_shops):
    """FILT-10: from > to → 400."""
    user = org_admin_with_shops["user"]
    org_id = org_admin_with_shops["org"].id
    today = date.today()
    req = _make_request(
        {
            "range": "custom",
            "from": today.isoformat(),
            "to": (today - timedelta(days=10)).isoformat(),
        }
    )
    with pytest.raises(ValidationError):
        validate_filter_params(request=req, user=user, org_id=org_id)


def test_filter_hash_differs_by_shop_scope():
    """TECH-02 / DASH-C1: two users with different accessible_shop_ids must produce different filter_hash."""
    a = DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        accessible_shop_ids=(1, 2),
    )
    b = DashboardFilterParams(
        region_id=None,
        shop_id=None,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        accessible_shop_ids=(3, 4),
    )
    assert a.filter_hash() != b.filter_hash()


def test_filter_hash_stable_for_same_inputs():
    a = DashboardFilterParams(
        region_id=5,
        shop_id=None,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        accessible_shop_ids=(1, 2),
    )
    b = DashboardFilterParams(
        region_id=5,
        shop_id=None,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        accessible_shop_ids=(1, 2),
    )
    assert a.filter_hash() == b.filter_hash()
