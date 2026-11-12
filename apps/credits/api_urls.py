"""Credit API routes: Superadmin endpoints and the tenant shop-credits read.

Included under ``api/v1/`` in ``config/urls.py``.
"""

from __future__ import annotations

from django.urls import path

from apps.credits.views import BonusAllocationView, CreditShopListView, ShopCreditsView

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
    path(
        "shops/<int:shop_id>/credits/",
        ShopCreditsView.as_view(),
        name="shop-credits",
    ),
]
