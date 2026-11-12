"""AI cost explorer API routes (Superadmin). Included under ``api/v1/`` in ``config/urls.py``."""

from __future__ import annotations

from django.urls import path

from apps.integrations.openai.pricing_views import (
    AiPricingDetailView,
    AiPricingHistoryView,
    AiPricingListView,
    AiPricingMissingRefreshView,
    AiPricingMissingView,
    AiPricingSuggestionsView,
    AiPricingSyncStatusView,
    AiPricingSyncToggleView,
    AiPricingSyncTriggerView,
)
from apps.integrations.openai.views import (
    AiCostOrganisationListView,
    AiCostOrgModelsView,
    AiCostOrgShopsView,
    AiCostOrgSummaryView,
    AiCostSummaryView,
)

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
    path(
        "superadmin/ai-cost/organisations/<int:org_id>/summary/",
        AiCostOrgSummaryView.as_view(),
        name="superadmin-ai-cost-org-summary",
    ),
    path(
        "superadmin/ai-cost/organisations/<int:org_id>/shops/",
        AiCostOrgShopsView.as_view(),
        name="superadmin-ai-cost-org-shops",
    ),
    path(
        "superadmin/ai-cost/organisations/<int:org_id>/models/",
        AiCostOrgModelsView.as_view(),
        name="superadmin-ai-cost-org-models",
    ),
    path("superadmin/ai-pricing/", AiPricingListView.as_view(), name="superadmin-ai-pricing-list"),
    path(
        "superadmin/ai-pricing/<int:pk>/",
        AiPricingDetailView.as_view(),
        name="superadmin-ai-pricing-detail",
    ),
    path(
        "superadmin/ai-pricing/history/",
        AiPricingHistoryView.as_view(),
        name="superadmin-ai-pricing-history",
    ),
    path(
        "superadmin/ai-pricing/model-suggestions/",
        AiPricingSuggestionsView.as_view(),
        name="superadmin-ai-pricing-suggestions",
    ),
    path(
        "superadmin/ai-pricing/missing/",
        AiPricingMissingView.as_view(),
        name="superadmin-ai-pricing-missing",
    ),
    path(
        "superadmin/ai-pricing/missing/refresh/",
        AiPricingMissingRefreshView.as_view(),
        name="superadmin-ai-pricing-missing-refresh",
    ),
    path(
        "superadmin/ai-pricing/sync/status/",
        AiPricingSyncStatusView.as_view(),
        name="superadmin-ai-pricing-sync-status",
    ),
    path(
        "superadmin/ai-pricing/sync/toggle/",
        AiPricingSyncToggleView.as_view(),
        name="superadmin-ai-pricing-sync-toggle",
    ),
    path(
        "superadmin/ai-pricing/sync/trigger/",
        AiPricingSyncTriggerView.as_view(),
        name="superadmin-ai-pricing-sync-trigger",
    ),
]
