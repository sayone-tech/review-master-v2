from __future__ import annotations

from django.urls import path

from apps.organisations.views import org_admin_dashboard, organisation_list

urlpatterns = [
    path("admin/organisations/", organisation_list, name="organisation_list"),
    path("admin/org-dashboard/", org_admin_dashboard, name="org_admin_dashboard"),
]
