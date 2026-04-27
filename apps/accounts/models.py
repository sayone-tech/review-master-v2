from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.accounts.managers import UserManager
from apps.common.models import TimeStampedModel


def _default_invitation_expiry() -> datetime:
    return timezone.now() + timedelta(hours=48)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Superadmin"
        ORG_ADMIN = "ORG_ADMIN", "Org Admin"
        STAFF_ADMIN = "STAFF_ADMIN", "Staff Admin"

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, db_index=True)
    organisation = models.ForeignKey(
        "organisations.Organisation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    email_suppressed = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_users",
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["full_name"]

    objects: UserManager = UserManager()

    class Meta:
        db_table = "accounts_user"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        return self.email


class InvitationToken(TimeStampedModel):
    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="invitation_tokens",
    )
    invited_user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitation_token",
    )

    class Purpose(models.TextChoices):
        ORG_ADMIN = "ORG_ADMIN", "Org Admin Setup"
        TEAM_MEMBER = "TEAM_MEMBER", "Team Member Invitation"

    class InvitedForRole(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Superadmin"
        ORG_ADMIN = "ORG_ADMIN", "Org Admin"
        STAFF_ADMIN = "STAFF_ADMIN", "Staff Admin"

    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(db_index=True, default=_default_invitation_expiry)
    purpose = models.CharField(  # noqa: DJ001 — expand-contract step 1, nullable for backfill
        max_length=20,
        choices=Purpose.choices,
        null=True,
        blank=True,
        db_index=True,
    )
    invited_for_role = models.CharField(  # noqa: DJ001 — expand-contract step 1, nullable for backfill
        max_length=20,
        choices=InvitedForRole.choices,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "accounts_invitation_token"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "is_used", "expires_at"],
                name="invite_org_used_exp_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"InvitationToken(org={self.organisation_id}, used={self.is_used})"

    @property
    def is_expired(self) -> bool:
        return bool(timezone.now() > self.expires_at)

    @classmethod
    def hash_token(cls, raw_token: str) -> str:
        """SHA-256 hex digest of the signed token string (stored, never the raw token)."""
        return hashlib.sha256(raw_token.encode()).hexdigest()


class StaffAccessScope(TimeStampedModel):
    class ScopeType(models.TextChoices):
        REGION = "REGION", "Region"
        SHOP = "SHOP", "Shop"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="access_scopes",
        limit_choices_to={"role": User.Role.STAFF_ADMIN},
    )
    scope_type = models.CharField(max_length=10, choices=ScopeType.choices, db_index=True)
    # String FK labels avoid circular imports (accounts -> regions/shops disallowed)
    region = models.ForeignKey(
        "regions.Region",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="staff_scopes",
    )
    shop = models.ForeignKey(
        "shops.Shop",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="staff_scopes",
    )

    class Meta:
        db_table = "accounts_staff_access_scope"
        ordering: ClassVar[list[str]] = ["-created_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(
                    models.Q(scope_type="REGION", region__isnull=False, shop__isnull=True)
                    | models.Q(scope_type="SHOP", shop__isnull=False, region__isnull=True)
                ),
                name="staff_scope_xor_region_shop",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["user", "scope_type"], name="staff_scope_user_type_idx"),
        ]

    def __str__(self) -> str:
        return f"StaffAccessScope(user={self.user_id}, type={self.scope_type})"
