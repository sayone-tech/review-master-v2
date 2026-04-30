from __future__ import annotations

from typing import Any, cast

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.exceptions import LastManagerError
from apps.accounts.forms import (
    ActivationForm,
    CustomAuthenticationForm,
    ProfileNameForm,
    ProfilePasswordChangeForm,
)
from apps.accounts.models import InvitationToken, User
from apps.accounts.permissions import IsOrgAdmin, org_admin_required
from apps.accounts.selectors.team import get_team_stats, list_team_members
from apps.accounts.serializers import (
    TeamMemberCreateSerializer,
    TeamMemberReadSerializer,
    TeamMemberUpdateSerializer,
)
from apps.accounts.services.profile import change_password as svc_change_password
from apps.accounts.services.profile import update_profile_name
from apps.accounts.services.team import (
    disable_member,
    enable_member,
    invite_member,
    remove_member,
    resend_team_invitation,
    send_team_invitation_email,
    update_member,
)
from apps.accounts.throttling import LoginRateThrottle
from apps.common.permissions import IsOrgScoped
from apps.common.viewsets import TenantScopedViewSet

SESSION_AGE_24H = 60 * 60 * 24
SESSION_AGE_30D = 60 * 60 * 24 * 30
RATE_LIMIT_MESSAGE = "Too many sign-in attempts. Please try again in 15 minutes."


# ---------------------------------------------------------------------------
# DRF: TeamViewSet
# ---------------------------------------------------------------------------


class TeamPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class TeamViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    """Team management API: list/create/update/destroy + disable/enable/resend/stats.

    Scoped to the authenticated user's organisation via TenantScopedViewSet.
    Only ORG_ADMIN users may access this viewset (IsOrgAdmin).
    """

    permission_classes = [IsOrgAdmin, IsOrgScoped]  # noqa: RUF012
    pagination_class = TeamPagination
    lookup_field = "pk"

    def get_serializer_class(
        self,
    ) -> (
        type[TeamMemberReadSerializer]
        | type[TeamMemberCreateSerializer]
        | type[TeamMemberUpdateSerializer]
    ):
        if self.action == "create":
            return TeamMemberCreateSerializer
        if self.action in {"update", "partial_update"}:
            return TeamMemberUpdateSerializer
        return TeamMemberReadSerializer

    def get_queryset(self) -> Any:
        org_id = getattr(self.request.user, "organisation_id", None)
        if org_id is None:
            return User.objects.none()
        region_id_str = self.request.query_params.get("region_id") or None
        shop_id_str = self.request.query_params.get("shop_id") or None
        region_id: int | None = int(region_id_str) if region_id_str else None
        shop_id: int | None = int(shop_id_str) if shop_id_str else None
        return list_team_members(
            organisation_id=org_id,
            search=self.request.query_params.get("search", ""),
            region_id=region_id,
            shop_id=shop_id,
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        caller = cast("User", request.user)
        org = caller.organisation  # IsOrgAdmin ensures this is set
        if org is None:
            return Response({"detail": "Organisation required."}, status=status.HTTP_403_FORBIDDEN)
        user, raw_token = invite_member(
            organisation=org,
            full_name=serializer.validated_data["full_name"],
            email=serializer.validated_data["email"],
            invited_for_role=serializer.validated_data["invited_for_role"],
            region_ids=serializer.validated_data.get("region_ids", []),
            shop_ids=serializer.validated_data.get("shop_ids", []),
            invited_by=caller,
        )
        scopes = list(user.access_scopes.select_related("region", "shop").all())
        send_team_invitation_email(
            member=user,
            raw_token=raw_token,
            inviter=caller,
            scopes=scopes,
            is_resend=False,
        )
        read = TeamMemberReadSerializer(user).data
        return Response(read, status=status.HTTP_201_CREATED)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = False
        return self._do_update(request, *args, **kwargs)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self._do_update(request, *args, **kwargs)

    def _do_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        member = self.get_object()
        # Self-demotion guard
        if member.pk == request.user.pk and request.data.get("role") == User.Role.STAFF_ADMIN:
            return Response(
                {"detail": "You cannot demote yourself."}, status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        # Last-manager guard on demotion
        if (
            member.role == User.Role.ORG_ADMIN
            and serializer.validated_data["role"] == User.Role.STAFF_ADMIN
        ):
            peer_managers = (
                User.objects.filter(
                    organisation_id=member.organisation_id,
                    role=User.Role.ORG_ADMIN,
                    is_active=True,
                )
                .exclude(pk=member.pk)
                .count()
            )
            if peer_managers == 0:
                return Response(
                    {"detail": "Cannot remove the last Manager."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        update_member(
            member=member,
            full_name=serializer.validated_data["full_name"],
            role=serializer.validated_data["role"],
            region_ids=serializer.validated_data.get("region_ids", []),
            shop_ids=serializer.validated_data.get("shop_ids", []),
        )
        member.refresh_from_db()
        return Response(TeamMemberReadSerializer(member).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        member = self.get_object()
        if member.pk == request.user.pk:
            return Response(
                {"detail": "You cannot remove yourself."}, status=status.HTTP_403_FORBIDDEN
            )
        try:
            remove_member(member=member, removed_by=cast("User", request.user))
        except LastManagerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="disable")
    def disable(self, request: Request, pk: int | None = None) -> Response:
        member = self.get_object()
        if member.pk == request.user.pk:
            return Response(
                {"detail": "You cannot disable yourself."}, status=status.HTTP_403_FORBIDDEN
            )
        disable_member(member=member)
        return Response(TeamMemberReadSerializer(member).data)

    @action(detail=True, methods=["post"], url_path="enable")
    def enable(self, request: Request, pk: int | None = None) -> Response:
        member = self.get_object()
        enable_member(member=member)
        return Response(TeamMemberReadSerializer(member).data)

    @action(detail=True, methods=["post"], url_path="resend")
    def resend(self, request: Request, pk: int | None = None) -> Response:
        member = self.get_object()
        caller = cast("User", request.user)
        raw_token = resend_team_invitation(member=member, resented_by=caller)
        scopes = list(member.access_scopes.select_related("region", "shop").all())
        send_team_invitation_email(
            member=member,
            raw_token=raw_token,
            inviter=caller,
            scopes=scopes,
            is_resend=True,
        )
        return Response(TeamMemberReadSerializer(member).data)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request: Request) -> Response:
        org_id = getattr(request.user, "organisation_id", None)
        if org_id is None:
            return Response({"total_members": 0, "managers": 0, "active_members": 0})
        return Response(get_team_stats(organisation_id=org_id))


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/profile.html")


class CustomLoginView(LoginView):
    """Rate-limited LoginView with remember-me session expiry.

    - POST throttled by LoginRateThrottle (10/15min per IP, Redis DB 1)
    - GET never throttled (override post() only)
    - remember_me checkbox: checked → 30d session; unchecked → 24h session
    - redirect_authenticated_user = True: already-logged-in users land on LOGIN_REDIRECT_URL
    """

    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        throttle = LoginRateThrottle()
        if not throttle.allow_request(request, self):  # type: ignore[arg-type]
            return HttpResponse(
                RATE_LIMIT_MESSAGE, status=429, content_type="text/plain; charset=utf-8"
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form: CustomAuthenticationForm) -> HttpResponse:  # type: ignore[override]
        remember = self.request.POST.get("remember_me")
        # Call super() FIRST — it logs the user in and creates the session.
        response = super().form_valid(form)
        # Session expiry MUST be set after super() (super creates a fresh session).
        if remember:
            self.request.session.set_expiry(SESSION_AGE_30D)
        else:
            self.request.session.set_expiry(SESSION_AGE_24H)
        # Role-based redirect overrides Django's get_success_url for known roles.
        # STAFF_ADMIN and edge cases fall through to the response from super()
        # which honours next= params and LOGIN_REDIRECT_URL.
        user = self.request.user
        if not isinstance(user, User):
            return response
        if user.role == User.Role.SUPERADMIN:
            return redirect("/admin/organisations/")
        if user.role == User.Role.ORG_ADMIN and getattr(user, "organisation_id", None) is not None:
            return redirect("/admin/org/dashboard/")
        return response


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Password-reset confirm view that redirects to /login/ with a flash."""

    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form: Any) -> HttpResponse:
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Password updated. Please sign in.",
        )
        return response


ACTV04_COPY = (
    "This invitation link is invalid or has expired. "
    "Please contact your administrator to request a new one."
)
ACTV05_COPY = "This invitation has already been used."


def invite_accept_view(request: HttpRequest, token: str) -> HttpResponse:
    """Public (no @login_required) — ACTV-01..05.

    Three token states (checked in this exact order):
    1. Not found or tamper: render invite_error with ACTV-04 copy
    2. is_used: render invite_error with ACTV-05 copy (CHECKED BEFORE expired)
    3. is_expired: render invite_error with ACTV-04 copy
    4. Valid: render activation form (GET) or process it (POST)

    On POST success: activate_account(), login(user), redirect org_admin_dashboard.
    """
    token_hash = InvitationToken.hash_token(token)
    try:
        invitation = InvitationToken.objects.select_related("organisation").get(
            token_hash=token_hash
        )
    except InvitationToken.DoesNotExist:
        return render(request, "accounts/invite_error.html", {"message": ACTV04_COPY})

    # CRITICAL ORDER: is_used FIRST, then is_expired. A resend makes the old token
    # is_used=True while leaving expires_at untouched — we want ACTV-05 copy in that case.
    if invitation.is_used:
        return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
    if invitation.is_expired:
        return render(request, "accounts/invite_error.html", {"message": ACTV04_COPY})

    organisation = invitation.organisation

    if request.method == "POST":
        form = ActivationForm(request.POST)
        if form.is_valid():
            if invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER:
                from apps.accounts.services.team import activate_team_member

                try:
                    user = activate_team_member(
                        invitation=invitation,
                        full_name=form.cleaned_data["full_name"],
                        password=form.cleaned_data["password1"],
                    )
                except ValidationError:
                    return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
                login(request, user)
                if user.role == User.Role.STAFF_ADMIN:
                    return redirect(reverse("org_welcome"))
                return redirect(reverse("org_admin_dashboard"))
            # ORG_ADMIN path — existing code unchanged
            from apps.organisations.services.organisations import activate_account

            try:
                user = activate_account(
                    invitation=invitation,
                    full_name=form.cleaned_data["full_name"],
                    password=form.cleaned_data["password1"],
                )
            except ValidationError:
                # Race: someone else activated between is_used check and now.
                return render(request, "accounts/invite_error.html", {"message": ACTV05_COPY})
            login(request, user)
            return redirect(reverse("org_admin_dashboard"))
    else:
        # GET branch — pre-fill form for TEAM_MEMBER invites
        if (
            invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER
            and invitation.invited_user is not None
        ):
            form = ActivationForm(initial={"full_name": invitation.invited_user.full_name})
        else:
            form = ActivationForm()

    # Choose template and email based on invitation purpose
    if invitation.purpose == InvitationToken.Purpose.TEAM_MEMBER:
        template = "accounts/team_invite_accept.html"
        email_to_show = (
            invitation.invited_user.email
            if invitation.invited_user is not None
            else organisation.email
        )
        role_context = {
            "role_display": ("Manager" if invitation.invited_for_role == "ORG_ADMIN" else "Staff"),
            "is_staff": invitation.invited_for_role == "STAFF_ADMIN",
        }
    else:
        template = "accounts/invite_accept.html"
        email_to_show = organisation.email
        role_context = None

    return render(
        request,
        template,
        {
            "form": form,
            "organisation": organisation,
            "email": email_to_show,
            "role_context": role_context,
            "invitation": invitation,
        },
    )


@login_required
def update_name_view(request: HttpRequest) -> HttpResponse:
    """PROF-01 — POST-only name update."""
    if request.method != "POST":
        return redirect("profile")
    form = ProfileNameForm(request.POST)
    if form.is_valid():
        user = cast("User", request.user)  # @login_required guarantees authenticated
        update_profile_name(
            user=user,
            full_name=form.cleaned_data["full_name"],
        )
        messages.success(request, "Name updated.")
        return redirect("profile")
    return render(
        request,
        "accounts/profile.html",
        {"name_form": form, "pw_form": ProfilePasswordChangeForm(), "page_title": "Profile"},
    )


@login_required
def change_password_view(request: HttpRequest) -> HttpResponse:
    """PROF-02 — POST-only password change."""
    if request.method != "POST":
        return redirect("profile")
    form = ProfilePasswordChangeForm(request.POST)
    if form.is_valid():
        user = cast("User", request.user)  # @login_required guarantees authenticated
        try:
            svc_change_password(
                user=user,
                current_password=form.cleaned_data["current_password"],
                new_password=form.cleaned_data["new_password"],
            )
        except ValueError:
            form.add_error("current_password", "Current password is incorrect.")
            return render(
                request,
                "accounts/profile.html",
                {"name_form": ProfileNameForm(), "pw_form": form, "page_title": "Profile"},
            )
        update_session_auth_hash(request, user)
        messages.success(request, "Password updated.")
        return redirect("profile")
    return render(
        request,
        "accounts/profile.html",
        {"name_form": ProfileNameForm(), "pw_form": form, "page_title": "Profile"},
    )


@org_admin_required
def org_profile(request: HttpRequest) -> HttpResponse:
    """Org Admin profile page — /admin/org/profile/.

    Mirrors the Superadmin `profile` view exactly but renders inside base_org.html.
    Reuses the same form classes and service functions.
    """
    return render(request, "accounts/org_profile.html", {"page_title": "Profile"})


@org_admin_required
def org_update_name_view(request: HttpRequest) -> HttpResponse:
    """POST-only Org Admin name update."""
    if request.method != "POST":
        return redirect("org_profile")
    form = ProfileNameForm(request.POST)
    if form.is_valid():
        user = cast("User", request.user)
        update_profile_name(
            user=user,
            full_name=form.cleaned_data["full_name"],
        )
        messages.success(request, "Name updated.")
        return redirect("org_profile")
    return render(
        request,
        "accounts/org_profile.html",
        {"name_form": form, "pw_form": ProfilePasswordChangeForm(), "page_title": "Profile"},
    )


@org_admin_required
def org_change_password_view(request: HttpRequest) -> HttpResponse:
    """POST-only Org Admin password change."""
    if request.method != "POST":
        return redirect("org_profile")
    form = ProfilePasswordChangeForm(request.POST)
    if form.is_valid():
        user = cast("User", request.user)
        try:
            svc_change_password(
                user=user,
                current_password=form.cleaned_data["current_password"],
                new_password=form.cleaned_data["new_password"],
            )
        except ValueError:
            form.add_error("current_password", "Current password is incorrect.")
            return render(
                request,
                "accounts/org_profile.html",
                {"name_form": ProfileNameForm(), "pw_form": form, "page_title": "Profile"},
            )
        update_session_auth_hash(request, user)
        messages.success(request, "Password changed.")
        return redirect("org_profile")
    return render(
        request,
        "accounts/org_profile.html",
        {"name_form": ProfileNameForm(), "pw_form": form, "page_title": "Profile"},
    )
