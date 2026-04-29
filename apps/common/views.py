from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe — app is running."""
    return JsonResponse({"status": "ok"})


def readyz(request: HttpRequest) -> JsonResponse:
    """Readiness probe — DB and Redis reachable."""
    checks: dict[str, str] = {}
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = str(exc)
    try:
        cache.set("readyz_check", "1", 5)
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = str(exc)
    status = 200 if all(v == "ok" for v in checks.values()) else 503
    body: dict[str, str] = {"status": "ready" if status == 200 else "degraded", **checks}
    return JsonResponse(body, status=status)


def home(request: HttpRequest) -> HttpResponse:
    """Root URL handler — redirects authenticated users to their role dashboard.

    Unauthenticated users are sent to the login page.
    This replaces the Phase 1 placeholder that accidentally rendered a shell with
    hardcoded /stores/ and /reviews/ sidebar links for ORG_ADMIN users.
    """
    if not request.user.is_authenticated:
        return redirect("login")
    role = getattr(request.user, "role", None)
    if role == "SUPERADMIN":
        return redirect("organisation_list")
    # ORG_ADMIN and STAFF_ADMIN both land on the org dashboard.
    return redirect("org_admin_dashboard_v02")


def showcase(request: HttpRequest) -> HttpResponse:
    """Component showcase page at /__ui__/ — renders every design system primitive."""

    class _FakePaginator:
        count = 47
        page_range = range(1, 6)
        num_pages = 5

    class _FakePage:
        number = 1
        paginator = _FakePaginator()

        def start_index(self) -> int:
            return 1

        def end_index(self) -> int:
            return 8

        def has_previous(self) -> bool:
            return False

        def has_next(self) -> bool:
            return True

        def previous_page_number(self) -> int:
            return 1

        def next_page_number(self) -> int:
            return 2

    ctx = {
        "org_type_options": [
            ("", "Select one"),
            ("RETAIL", "Retail"),
            ("RESTAURANT", "Restaurant"),
            ("PHARMACY", "Pharmacy"),
            ("SUPERMARKET", "Supermarket"),
        ],
        "status_options": [("", "All statuses"), ("ACTIVE", "Active"), ("DISABLED", "Disabled")],
        "type_options": [("", "All types"), ("RETAIL", "Retail")],
        "fake_page_obj": _FakePage(),
    }
    return render(request, "pages/showcase.html", ctx)
