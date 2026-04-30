from __future__ import annotations

from django.urls import path

from apps.organisations.views import (
    org_admin_dashboard,
    org_welcome,
    organisation_list,
    team_list,
)
from apps.regions.views import region_list
from apps.shops.views import shop_list

urlpatterns = [
    path("admin/organisations/", organisation_list, name="organisation_list"),
    # Original URL — name preserved so invite_accept_view's reverse() keeps working.
    path("admin/org-dashboard/", org_admin_dashboard, name="org_admin_dashboard"),
    # New alias — sidebar + login redirect target. SAME view, second URL.
    path(
        "admin/org/dashboard/",
        org_admin_dashboard,
        name="org_admin_dashboard_v02",
    ),
    # Regions — Phase 7: real list view replaces Phase 6 stub.
    path(
        "admin/org/regions/",
        region_list,
        name="org_regions",
    ),
    # Shops — Phase 8: real list view replaces Phase 6 stub.
    path(
        "admin/org/shops/",
        shop_list,
        name="org_shops",
    ),
    # Team — Phase 9: real list view replaces Phase 6 stub.
    path(
        "admin/org/team/",
        team_list,
        name="org_team",
    ),
    # Staff welcome stub page — redirected to after TEAM_MEMBER acceptance.
    path(
        "admin/org/welcome/",
        org_welcome,
        name="org_welcome",
    ),
]
