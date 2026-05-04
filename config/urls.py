from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.action_items.urls import api_urlpatterns as action_items_api_urls
from apps.organisations.views import OrganisationViewSet
from apps.regions.views import RegionViewSet
from apps.reviews.views import ReviewViewSet
from apps.shops.views import ShopViewSet

# SimpleRouter avoids creating a browsable API-root at "/" which would conflict
# with the Django home view at apps/common/urls.py.
router = SimpleRouter()
router.register(r"api/v1/organisations", OrganisationViewSet, basename="organisation")
router.register(r"api/v1/regions", RegionViewSet, basename="region")
router.register(r"api/v1/shops", ShopViewSet, basename="shop")
router.register(r"api/v1/reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("", include(router.urls)),
    path("api/v1/", include(action_items_api_urls)),
    # NOTE: notifications API include is added by plan 13-05 once it creates
    # apps/notifications/urls.py. Django's `include("string")` resolves
    # eagerly at import time (the plan's "lazy include" assumption was
    # incorrect), so wiring the include here would break `manage.py check`
    # before 13-05 commits. 13-05 owns apps/notifications/urls.py outright.
    path("api/v1/", include("apps.accounts.api_urls")),
    path("", include("apps.organisations.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
    path("", include("apps.shops.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.action_items.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
