from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def organisation_list(request: HttpRequest) -> HttpResponse:
    """Organisation list — placeholder until Phase 3 ships the real view.

    Protected by @login_required so unauthenticated GETs redirect to
    LOGIN_URL (/login/) per AUTH-05 requirements.
    """
    return render(request, "pages/placeholder.html")
