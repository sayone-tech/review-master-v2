from __future__ import annotations

from django.urls import path

from apps.integrations.openai.views import ai_cost_page, ai_pricing_page

urlpatterns = [
    path("admin/ai-cost/", ai_cost_page, name="ai_cost_explorer"),
    path(
        "admin/ai-cost/organisations/<int:org_id>/",
        ai_cost_page,
        name="ai_cost_org_detail",
    ),
    path("admin/ai-pricing/", ai_pricing_page, name="ai_pricing_page"),
]
