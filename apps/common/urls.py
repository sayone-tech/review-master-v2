from django.urls import path

from apps.common.views import healthz, home, logout_stub, readyz, showcase

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("logout/", logout_stub, name="logout"),
    path("__ui__/", showcase, name="showcase"),
]
