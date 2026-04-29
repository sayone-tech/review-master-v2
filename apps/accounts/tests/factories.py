from __future__ import annotations

import secrets

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import InvitationToken, StaffAccessScope, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = User.Role.SUPERADMIN
    organisation = None  # opt-in via UserFactory(organisation=org)
    is_active = True
    is_staff = False

    @factory.post_generation  # type: ignore[misc]
    def password(self, create: bool, extracted: str | None, **kwargs: object) -> None:
        if not create:
            return
        self.set_password(extracted or "testpass1234")
        self.save()


class OrgAdminFactory(UserFactory):
    role = User.Role.ORG_ADMIN


class StaffAdminFactory(UserFactory):
    role = User.Role.STAFF_ADMIN


class InvitationTokenFactory(DjangoModelFactory):
    class Meta:
        model = InvitationToken

    organisation = factory.SubFactory("apps.organisations.tests.factories.OrganisationFactory")
    token_hash = factory.LazyAttribute(
        lambda _: InvitationToken.hash_token(secrets.token_urlsafe(32))
    )
    is_used = False
    purpose = InvitationToken.Purpose.ORG_ADMIN
    invited_for_role = InvitationToken.InvitedForRole.ORG_ADMIN


class StaffAccessScopeFactory(DjangoModelFactory):
    class Meta:
        model = StaffAccessScope

    user = factory.SubFactory(UserFactory, role=User.Role.STAFF_ADMIN)
    scope_type = StaffAccessScope.ScopeType.REGION
    region = factory.SubFactory("apps.regions.tests.factories.RegionFactory")
    shop = None
