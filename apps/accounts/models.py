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
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(db_index=True, default=_default_invitation_expiry)

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
