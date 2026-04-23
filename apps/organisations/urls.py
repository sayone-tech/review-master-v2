from __future__ import annotations

from django.urls import path

from apps.organisations.views import organisation_list

urlpatterns = [
    path("admin/organisations/", organisation_list, name="organisation_list"),
]
