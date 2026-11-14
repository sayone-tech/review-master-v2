from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from apps.insights.views import InsightsBookApiView, insights_page_view

api_urlpatterns: list[URLPattern | URLResolver] = [
    path("", InsightsBookApiView.as_view(), name="insights-book"),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/org/insights/", insights_page_view, name="org_insights"),
]
