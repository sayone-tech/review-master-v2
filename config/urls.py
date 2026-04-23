from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.organisations.views import OrganisationViewSet

# SimpleRouter avoids creating a browsable API-root at "/" which would conflict
# with the Django home view at apps/common/urls.py.
router = SimpleRouter()
router.register(r"api/v1/organisations", OrganisationViewSet, basename="organisation")

urlpatterns = [
    path("", include(router.urls)),
    path("", include("apps.organisations.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar  # type: ignore[import-not-found]

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
