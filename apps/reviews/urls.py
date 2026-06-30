"""Phase 11 — Reviews template view URLs.

Phase 25 Plan 02 — tags page URL.
API router registrations (canonical-tags, tag-merge-jobs) live in config/urls.py
so they are ordered before the ReviewViewSet to avoid PK-shadowing.
"""

from __future__ import annotations

from django.urls import path

from apps.reviews.views import review_list, tags_page_view

urlpatterns = [
    path("admin/org/reviews/", review_list, name="org_review_list"),
    # Phase 25 Plan 02: Tags management page (ORG_ADMIN only via @org_admin_required)
    path("admin/org/tags/", tags_page_view, name="org_tags_page"),
]
