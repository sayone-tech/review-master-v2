from __future__ import annotations

from django.urls import path

from apps.organisations.views import (
    org_admin_dashboard,
    org_stub_view,
    organisation_list,
)
from apps.regions.views import region_list

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
    # Stub pages — Phases 8/9 will replace each view but keep these URL names.
    path(
        "admin/org/shops/",
        org_stub_view,
        kwargs={"section": "shops"},
        name="org_shops",
    ),
    path(
        "admin/org/team/",
        org_stub_view,
        kwargs={"section": "team"},
        name="org_team",
    ),
]
