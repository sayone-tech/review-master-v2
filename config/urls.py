from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from rest_framework.authentication import SessionAuthentication
from rest_framework.routers import SimpleRouter

from apps.accounts.permissions import IsSuperadmin
from apps.action_items.urls import api_urlpatterns as action_items_api_urls
from apps.common.views import AuditLogViewSet, ScalarDocsView
from apps.notifications.urls import api_urlpatterns as notifications_api_urls
from apps.organisations.views import OrganisationViewSet
from apps.regions.views import RegionViewSet
from apps.reply_templates.views import ReplyTemplateViewSet
from apps.reports.urls import api_urlpatterns as reports_api_urls
from apps.reviews.views import (
    OrgCanonicalTagViewSet,
    ReviewViewSet,
    SyncProgressSnapshotView,
    TagMergeJobViewSet,
)
from apps.shops.views import ReviewTargetViewSet, ShopViewSet

# SimpleRouter avoids creating a browsable API-root at "/" which would conflict
# with the Django home view at apps/common/urls.py.
router = SimpleRouter()
router.register(r"api/v1/organisations", OrganisationViewSet, basename="organisation")
router.register(r"api/v1/regions", RegionViewSet, basename="region")
router.register(r"api/v1/reply-templates", ReplyTemplateViewSet, basename="reply-template")
router.register(
    r"api/v1/shops/(?P<shop_pk>[^/.]+)/targets",
    ReviewTargetViewSet,
    basename="shop-target",
)
router.register(r"api/v1/shops", ShopViewSet, basename="shop")
# Phase 25 Plan 02: canonical-tags + tag-merge-jobs MUST be registered BEFORE
# reviews so the router prefix /api/v1/reviews/<pk>/ doesn't swallow these routes.
# Phase 27 Plan 01: sync-progress MUST also be registered BEFORE the reviews router prefix.
router.register(r"api/v1/reviews/canonical-tags", OrgCanonicalTagViewSet, basename="canonical-tags")
router.register(r"api/v1/reviews/tag-merge-jobs", TagMergeJobViewSet, basename="tag-merge-jobs")
router.register(r"api/v1/reviews", ReviewViewSet, basename="review")
router.register(r"api/v1/audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("", include(router.urls)),
    # Phase 27 Plan 01 — sync progress snapshot GET (SYNC-REL-01, D-01).
    # Registered as a plain path (not via router) because it is a single GET with a
    # URL argument — no list/create/update actions warranting a ViewSet/router registration.
    path(
        "api/v1/reviews/sync-progress/<int:shop_id>/",
        SyncProgressSnapshotView.as_view(),
        name="sync-progress-snapshot",
    ),
    path("api/v1/", include(action_items_api_urls)),
    path("api/v1/", include(notifications_api_urls)),
    path("api/v1/", include("apps.accounts.api_urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/reports/", include(reports_api_urls)),
    path("", include("apps.reports.urls")),
    # API documentation — Superadmin only, session auth only (no JWT access to docs)
    path(
        "api/v1/schema/",
        SpectacularAPIView.as_view(
            permission_classes=[IsSuperadmin],
            authentication_classes=[SessionAuthentication],
        ),
        name="schema",
    ),
    path("api/v1/schema/scalar/", ScalarDocsView.as_view(), name="schema-scalar"),
    path(
        "api/v1/schema/redoc/",
        SpectacularRedocView.as_view(
            permission_classes=[IsSuperadmin],
            authentication_classes=[SessionAuthentication],
        ),
        name="schema-redoc",
    ),
    path("", include("apps.organisations.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
    path("", include("apps.shops.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.action_items.urls")),
    path("django-admin/", admin.site.urls),
]

handler404 = "apps.common.views.page_not_found"
handler500 = "apps.common.views.server_error"

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
