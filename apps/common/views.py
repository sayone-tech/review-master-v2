from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render


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
    """Phase 1 placeholder landing page — renders the shell."""
    return render(request, "pages/placeholder.html")


def logout_stub(request: HttpRequest) -> HttpResponseRedirect:
    """Phase-1 placeholder for the logout endpoint.

    Provides a resolvable target for `{% url 'logout' %}` in sidebar.html and
    topbar.html so Django auth URLs do not need to be wired in Phase 1.

    Phase 2 replaces the body with the real logout flow (e.g. LogoutView) while
    keeping the URL name `logout` stable — no template changes required.

    Accepts GET and POST. Responds with a 302 to `/` (home).
    """
    return HttpResponseRedirect("/")
