from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User


class IsSuperadmin(BasePermission):
    """Allow only authenticated users whose role is SUPERADMIN."""

    message = "Superadmin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(getattr(user, "role", None) == User.Role.SUPERADMIN)


class IsOrgAdmin(BasePermission):
    """Allow only authenticated ORG_ADMIN users who have an organisation."""

    message = "Organisation Admin role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(
            getattr(user, "role", None) == User.Role.ORG_ADMIN
            and getattr(user, "organisation_id", None) is not None
        )


def org_admin_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Template-view decorator: requires ORG_ADMIN with organisation; else 403.

    Wrong-role users (SUPERADMIN, STAFF_ADMIN, org-less ORG_ADMIN) get
    HttpResponseForbidden — NOT a redirect. Anonymous users get the standard
    login redirect via @login_required.
    """
    from django.contrib.auth.decorators import login_required

    @login_required
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = request.user
        if not isinstance(user, User):
            return HttpResponseRedirect("/login/")
        if user.role != User.Role.ORG_ADMIN or user.organisation_id is None:
            return HttpResponseForbidden("Organisation Admin role required.")
        return view_func(request, *args, **kwargs)

    return wrapper
