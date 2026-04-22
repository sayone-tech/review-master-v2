from django.urls import path

from apps.common.views import healthz, readyz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
]
