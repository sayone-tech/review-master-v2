"""AI cost explorer API routes (Superadmin). Included under ``api/v1/`` in ``config/urls.py``."""

from __future__ import annotations

from django.urls import path

from apps.integrations.openai.views import AiCostOrganisationListView, AiCostSummaryView

urlpatterns = [
    path(
        "superadmin/ai-cost/summary/",
        AiCostSummaryView.as_view(),
        name="superadmin-ai-cost-summary",
    ),
    path(
        "superadmin/ai-cost/organisations/",
        AiCostOrganisationListView.as_view(),
        name="superadmin-ai-cost-orgs",
    ),
]
