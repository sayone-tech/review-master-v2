"""Phase 11 — Reviews template view URL."""

from __future__ import annotations

from django.urls import path

from apps.reviews.views import review_list

urlpatterns = [
    path("admin/org/reviews/", review_list, name="org_review_list"),
]
