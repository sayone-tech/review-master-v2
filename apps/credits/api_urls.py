"""Superadmin credit API routes, included under ``api/v1/`` in ``config/urls.py``."""

from __future__ import annotations

from django.urls import path

from apps.credits.views import BonusAllocationView, CreditShopListView

urlpatterns = [
    path(
        "superadmin/organisations/<int:org_id>/credits/shops/",
        CreditShopListView.as_view(),
        name="superadmin-credit-shops",
    ),
    path(
        "superadmin/shops/<int:shop_id>/credits/bonus/",
        BonusAllocationView.as_view(),
        name="superadmin-credit-bonus",
    ),
]
