from django.urls import path

from apps.common.views import healthz, home, readyz

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
]
