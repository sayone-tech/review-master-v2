from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from apps.reports.views import StoreReportApiView, reports_page_view

api_urlpatterns: list[URLPattern | URLResolver] = [
    path("stores/", StoreReportApiView.as_view(), name="store-report-api"),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/org/reports/", reports_page_view, name="org_reports"),
]
