from __future__ import annotations

import datetime

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import ReviewTarget
from apps.shops.services.targets import create_target, delete_target, update_target
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


@pytest.mark.django_db
class TestCreateTarget:
    def test_creates_with_month_anchor(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        t = create_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 15),  # mid-month, should normalise to 1st
            target_count=100,
            created_by=admin,
        )
        assert t.period_start == datetime.date(2026, 5, 1)
        assert t.target_count == 100
        assert t.organisation_id == shop.organisation_id

    def test_creates_with_week_anchor(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        # Wednesday 2026-05-13 should normalise to Monday 2026-05-11
        t = create_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.WEEK,
            period_start=datetime.date(2026, 5, 13),
            target_count=50,
            created_by=admin,
        )
        assert t.period_start == datetime.date(2026, 5, 11)

    def test_rejects_past_month_period(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        with pytest.raises(ValueError, match=r"Cannot set targets for past periods\."):
            create_target(
                shop_id=shop.pk,
                org_id=shop.organisation_id,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=datetime.date(2026, 4, 1),  # April — past
                target_count=100,
                created_by=admin,
            )

    def test_rejects_target_count_zero(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        with pytest.raises(ValueError, match=r"Target must be at least 1 review\."):
            create_target(
                shop_id=shop.pk,
                org_id=shop.organisation_id,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=datetime.date(2026, 5, 1),
                target_count=0,
                created_by=admin,
            )

    def test_rejects_duplicate_period(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        create_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=100,
            created_by=admin,
        )
        with pytest.raises(ValueError, match=r"A target for this period already exists\."):
            create_target(
                shop_id=shop.pk,
                org_id=shop.organisation_id,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=datetime.date(2026, 5, 1),
                target_count=200,
                created_by=admin,
            )

    def test_org_mismatch_raises(self):
        shop = ShopFactory()
        other_org = OrganisationFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=other_org)
        with pytest.raises(ReviewTarget.DoesNotExist):
            create_target(
                shop_id=shop.pk,
                org_id=other_org.pk,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=datetime.date(2026, 5, 1),
                target_count=100,
                created_by=admin,
            )


@pytest.mark.django_db
class TestUpdateTarget:
    def test_updates_target_count(self):
        t = ReviewTargetFactory(target_count=100)
        updated = update_target(target_id=t.pk, org_id=t.organisation_id, target_count=200)
        assert updated.target_count == 200

    def test_rejects_count_zero(self):
        t = ReviewTargetFactory()
        with pytest.raises(ValueError, match=r"Target must be at least 1 review\."):
            update_target(target_id=t.pk, org_id=t.organisation_id, target_count=0)

    def test_org_isolation(self):
        t = ReviewTargetFactory()
        other_org = OrganisationFactory()
        with pytest.raises(ReviewTarget.DoesNotExist):
            update_target(target_id=t.pk, org_id=other_org.pk, target_count=50)


@pytest.mark.django_db
class TestDeleteTarget:
    def test_deletes_target(self):
        t = ReviewTargetFactory()
        delete_target(target_id=t.pk, org_id=t.organisation_id)
        assert not ReviewTarget.objects.filter(pk=t.pk).exists()

    def test_org_isolation(self):
        t = ReviewTargetFactory()
        other_org = OrganisationFactory()
        with pytest.raises(ReviewTarget.DoesNotExist):
            delete_target(target_id=t.pk, org_id=other_org.pk)
