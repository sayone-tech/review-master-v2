from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import ReviewTarget
from apps.shops.services.targets import delete_target, set_target
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


@pytest.mark.django_db
class TestSetTarget:
    def test_creates_when_no_target_exists(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        t = set_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=100,
            created_by=admin,
        )
        assert t.pk is not None
        assert t.target_count == 100
        assert t.period_type == "MONTH"
        assert ReviewTarget.objects.filter(shop=shop, period_type="MONTH").count() == 1

    def test_updates_when_target_exists(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        t1 = set_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=50,
            created_by=admin,
        )
        t2 = set_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=200,
            created_by=admin,
        )
        assert t1.pk == t2.pk  # same row updated
        assert ReviewTarget.objects.filter(shop=shop, period_type="MONTH").count() == 1
        t2.refresh_from_db()
        assert t2.target_count == 200

    def test_week_and_month_are_independent(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        set_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.WEEK,
            target_count=10,
            created_by=admin,
        )
        set_target(
            shop_id=shop.pk,
            org_id=shop.organisation_id,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=40,
            created_by=admin,
        )
        assert ReviewTarget.objects.filter(shop=shop).count() == 2

    def test_rejects_target_count_zero(self):
        shop = ShopFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=shop.organisation)
        with pytest.raises(ValueError, match=r"Target must be at least 1 review\."):
            set_target(
                shop_id=shop.pk,
                org_id=shop.organisation_id,
                period_type=ReviewTarget.PeriodType.MONTH,
                target_count=0,
                created_by=admin,
            )

    def test_rejects_shop_from_another_org(self):
        shop = ShopFactory()
        other_org = OrganisationFactory()
        admin = UserFactory(role="ORG_ADMIN", organisation=other_org)
        with pytest.raises(ReviewTarget.DoesNotExist):
            set_target(
                shop_id=shop.pk,
                org_id=other_org.pk,
                period_type=ReviewTarget.PeriodType.MONTH,
                target_count=100,
                created_by=admin,
            )


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
