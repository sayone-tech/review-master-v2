from django.urls import path

from apps.common.views import audit_log_view, healthz, home, readyz, showcase

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("__ui__/", showcase, name="showcase"),
    path("admin/org/activity-log/", audit_log_view, name="audit_log_list"),
]
