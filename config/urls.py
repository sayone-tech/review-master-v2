from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.organisations.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.common.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    import debug_toolbar  # type: ignore[import-not-found]

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
