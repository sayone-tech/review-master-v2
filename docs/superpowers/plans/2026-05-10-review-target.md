# Review Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow Org Admins to set weekly/monthly review count targets per shop and track live progress inside the Shop Details modal.

**Architecture:** New `ReviewTarget` model in `apps/shops/` (services/selectors pattern); a nested `ReviewTargetViewSet` registered as a custom action under `/api/v1/shops/{id}/targets/`; three new React components (`useTargets.ts`, `TargetsTab.tsx`, `SetTargetModal.tsx`) plus a tab switcher added to `ShopDetailsModal.tsx`.

**Tech Stack:** Django 6 + DRF, factory-boy + pytest, React 18 + TypeScript (native fetch, no React Query — follow the pattern in `useShops.ts`)

---

## File Map

### New files
| File | Responsibility |
|------|----------------|
| `apps/shops/models.py` | Add `ReviewTarget` model (existing file, add class) |
| `apps/shops/migrations/NNNN_add_review_target.py` | Auto-generated migration |
| `apps/shops/selectors/targets.py` | `list_targets_for_shop` — returns targets with live progress |
| `apps/shops/services/targets.py` | `create_target`, `update_target`, `delete_target` |
| `apps/shops/serializers/targets.py` | `ReviewTargetReadSerializer`, `ReviewTargetCreateSerializer`, `ReviewTargetUpdateSerializer` |
| `apps/shops/tests/factories.py` | Add `ReviewTargetFactory` (existing file, append) |
| `apps/shops/tests/test_target_selectors.py` | Selector tests |
| `apps/shops/tests/test_target_services.py` | Service tests |
| `apps/shops/tests/test_target_views.py` | API tests |
| `frontend/src/widgets/shop-management/targetsApi.ts` | `listTargets`, `createTarget`, `patchTarget`, `deleteTarget` |
| `frontend/src/widgets/shop-management/useTargets.ts` | State hook — list + mutations |
| `frontend/src/widgets/shop-management/TargetsTab.tsx` | Tab body — progress cards |
| `frontend/src/widgets/shop-management/SetTargetModal.tsx` | Create form modal |

### Modified files
| File | Change |
|------|--------|
| `apps/shops/models.py` | Append `ReviewTarget` model class |
| `apps/shops/views.py` | Add `ReviewTargetViewSet` class |
| `config/urls.py` | Register `ReviewTargetViewSet` router |
| `apps/shops/tests/factories.py` | Append `ReviewTargetFactory` |
| `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` | Add tab state + `TargetsTab` |
| `frontend/src/widgets/shop-management/types.ts` | Add `TargetRow` type |

---

## Task 1: `ReviewTarget` Model + Migration

**Files:**
- Modify: `apps/shops/models.py`
- Create: migration (auto-generated)
- Create: `apps/shops/tests/factories.py` (append `ReviewTargetFactory`)

- [ ] **Step 1: Write the failing model test**

```python
# apps/shops/tests/test_models.py  (append to existing file)
import pytest
from datetime import date
from django.db import IntegrityError
from apps.shops.models import ReviewTarget
from apps.shops.tests.factories import ReviewTargetFactory
from apps.shops.tests.factories import ShopFactory
from apps.organisations.tests.factories import OrganisationFactory


@pytest.mark.django_db
class TestReviewTargetModel:
    def test_creates_with_valid_data(self):
        t = ReviewTargetFactory()
        assert t.pk is not None
        assert t.target_count >= 1

    def test_unique_constraint_prevents_duplicate_period(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=date(2026, 5, 1),
            target_count=100,
        )
        with pytest.raises(IntegrityError):
            ReviewTargetFactory(
                shop=shop,
                period_type=ReviewTarget.PeriodType.MONTH,
                period_start=date(2026, 5, 1),
                target_count=200,
            )

    def test_different_period_type_same_start_allowed(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=date(2026, 5, 1),
        )
        t2 = ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            period_start=date(2026, 5, 4),
        )
        assert t2.pk is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/renjith/Documents/Accounts/review-master
python -m pytest apps/shops/tests/test_models.py::TestReviewTargetModel -v
```
Expected: ImportError or AttributeError — `ReviewTarget` does not exist yet.

- [ ] **Step 3: Add `ReviewTarget` to `apps/shops/models.py`**

Append after the existing `ShopAuditLog` class:

```python
class ReviewTarget(TimeStampedModel):
    class PeriodType(models.TextChoices):
        WEEK = "WEEK", "Weekly"
        MONTH = "MONTH", "Monthly"

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="review_targets",
    )
    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="targets",
    )
    period_type = models.CharField(
        max_length=5,
        choices=PeriodType.choices,
        db_index=True,
    )
    period_start = models.DateField(db_index=True)
    target_count = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_targets",
    )

    class Meta:
        db_table = "shops_reviewtarget"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "period_type", "period_start"],
                name="target_unique_per_shop_period",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "shop", "period_type", "period_start"],
                name="target_org_shop_period_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"ReviewTarget({self.shop_id} {self.period_type} {self.period_start})"
```

- [ ] **Step 4: Add `ReviewTargetFactory` to `apps/shops/tests/factories.py`**

Append to existing file (add the import and class):

```python
from apps.shops.models import Shop, ShopAuditLog, ReviewTarget
import datetime

class ReviewTargetFactory(DjangoModelFactory):
    class Meta:
        model = ReviewTarget

    organisation = factory.LazyAttribute(lambda o: o.shop.organisation)
    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    period_type = ReviewTarget.PeriodType.MONTH
    period_start = datetime.date(2026, 5, 1)
    target_count = 100
    created_by = None
```

- [ ] **Step 5: Create and verify migration**

```bash
python manage.py makemigrations shops --name add_review_target
python manage.py migrate --run-syncdb
```
Expected: new migration file created, migration applies without errors.

- [ ] **Step 6: Run the model test**

```bash
python -m pytest apps/shops/tests/test_models.py::TestReviewTargetModel -v
```
Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/shops/models.py apps/shops/migrations/ apps/shops/tests/factories.py apps/shops/tests/test_models.py
git commit -m "feat(shops): add ReviewTarget model and factory"
```

---

## Task 2: Selector — `list_targets_for_shop` with Live Progress

**Files:**
- Create: `apps/shops/selectors/targets.py`
- Create: `apps/shops/tests/test_target_selectors.py`

- [ ] **Step 1: Write the failing selector tests**

```python
# apps/shops/tests/test_target_selectors.py
from __future__ import annotations

import datetime
import pytest
from apps.shops.models import ReviewTarget
from apps.shops.selectors.targets import list_targets_for_shop
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory


@pytest.mark.django_db
class TestListTargetsForShop:
    def test_returns_empty_list_when_no_targets(self):
        shop = ShopFactory()
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result == []

    def test_returns_target_with_computed_fields(self):
        shop = ShopFactory()
        t = ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=200,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert len(result) == 1
        row = result[0]
        assert row["id"] == t.pk
        assert row["period_type"] == "MONTH"
        assert row["period_start"] == datetime.date(2026, 5, 1)
        assert row["period_end"] == datetime.date(2026, 5, 31)
        assert row["target_count"] == 200
        assert row["received_count"] == 0
        assert row["pct"] == 0
        assert isinstance(row["days_remaining"], int)
        assert row["days_remaining"] >= 0

    def test_received_count_matches_reviews_in_period(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=10,
        )
        # 3 reviews inside the period
        for _ in range(3):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(2026, 5, 15, 12, 0, tzinfo=datetime.timezone.utc),
            )
        # 1 review outside the period (April)
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 4, 30, 12, 0, tzinfo=datetime.timezone.utc),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 3
        assert result[0]["pct"] == 30

    def test_soft_deleted_reviews_excluded_from_count(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=10,
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 5, 10, 12, 0, tzinfo=datetime.timezone.utc),
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(2026, 5, 10, 12, 0, tzinfo=datetime.timezone.utc),
            deleted_at=datetime.datetime(2026, 5, 11, tzinfo=datetime.timezone.utc),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 1

    def test_pct_capped_at_100(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
            target_count=2,
        )
        for _ in range(5):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(2026, 5, 5, 12, 0, tzinfo=datetime.timezone.utc),
            )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["pct"] == 100

    def test_org_isolation(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        shop_a = ShopFactory(organisation=org_a)
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b, organisation=org_b)
        result = list_targets_for_shop(shop_id=shop_a.pk, org_id=org_a.pk)
        assert result == []

    def test_week_period_end_is_sunday(self):
        shop = ShopFactory()
        # Monday 2026-05-11 → Sunday 2026-05-17
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            period_start=datetime.date(2026, 5, 11),
            target_count=50,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["period_end"] == datetime.date(2026, 5, 17)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/shops/tests/test_target_selectors.py -v
```
Expected: ImportError — `apps.shops.selectors.targets` does not exist.

- [ ] **Step 3: Create `apps/shops/selectors/targets.py`**

```python
from __future__ import annotations

import datetime
from math import floor

from django.db.models import Count, Q

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


def _period_end(period_type: str, period_start: datetime.date) -> datetime.date:
    if period_type == ReviewTarget.PeriodType.WEEK:
        return period_start + datetime.timedelta(days=6)  # Sunday
    # MONTH: last day of month
    if period_start.month == 12:
        return datetime.date(period_start.year + 1, 1, 1) - datetime.timedelta(days=1)
    return datetime.date(period_start.year, period_start.month + 1, 1) - datetime.timedelta(days=1)


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict]:
    """Return targets with live progress. Ordered: current first, future next, past last."""
    targets = list(
        ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id)
        .select_related()
        .order_by("period_start")
    )
    if not targets:
        return []

    today = datetime.date.today()

    # Build period boundaries for each target
    boundaries = [
        (t.pk, t.period_start, _period_end(t.period_type, t.period_start))
        for t in targets
    ]

    # Single aggregation query: count reviews per target period using conditional Count
    # Build a dict of {target_id: received_count} using a filter per target
    received_map: dict[int, int] = {t.pk: 0 for t in targets}
    for target_id, period_start, period_end in boundaries:
        count = Review.objects.filter(
            shop_id=shop_id,
            review_create_time__date__gte=period_start,
            review_create_time__date__lte=period_end,
            deleted_at__isnull=True,
        ).count()
        received_map[target_id] = count

    results = []
    for t in targets:
        period_end = _period_end(t.period_type, t.period_start)
        received = received_map[t.pk]
        pct = min(100, floor(received / t.target_count * 100)) if t.target_count > 0 else 0
        days_remaining = max(0, (period_end - today).days)
        results.append(
            {
                "id": t.pk,
                "period_type": t.period_type,
                "period_start": t.period_start,
                "period_end": period_end,
                "target_count": t.target_count,
                "received_count": received,
                "pct": pct,
                "days_remaining": days_remaining,
            }
        )

    # Sort: current periods first, future next, past last
    def _sort_key(row: dict) -> tuple:
        is_past = row["period_end"] < today
        is_future = row["period_start"] > today
        return (is_past, is_future, row["period_start"])

    results.sort(key=_sort_key)
    return results
```

- [ ] **Step 4: Run selector tests**

```bash
python -m pytest apps/shops/tests/test_target_selectors.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/shops/selectors/targets.py apps/shops/tests/test_target_selectors.py
git commit -m "feat(shops): add list_targets_for_shop selector with live progress"
```

---

## Task 3: Services — create, update, delete target

**Files:**
- Create: `apps/shops/services/targets.py`
- Create: `apps/shops/tests/test_target_services.py`

- [ ] **Step 1: Write the failing service tests**

```python
# apps/shops/tests/test_target_services.py
from __future__ import annotations

import datetime
import pytest
from apps.shops.models import ReviewTarget
from apps.shops.services.targets import create_target, delete_target, update_target
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory
from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory


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
        with pytest.raises(ValueError, match="Cannot set targets for past periods."):
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
        with pytest.raises(ValueError, match="Target must be at least 1 review."):
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
        with pytest.raises(ValueError, match="A target for this period already exists."):
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
        with pytest.raises(ValueError, match="Target must be at least 1 review."):
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/shops/tests/test_target_services.py -v
```
Expected: ImportError — `apps.shops.services.targets` does not exist.

- [ ] **Step 3: Create `apps/shops/services/targets.py`**

```python
from __future__ import annotations

import datetime

from django.db import IntegrityError

from apps.accounts.models import User
from apps.shops.models import ReviewTarget


def _anchor_month(d: datetime.date) -> datetime.date:
    return d.replace(day=1)


def _anchor_week(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())  # Monday


def _current_period_start(period_type: str) -> datetime.date:
    today = datetime.date.today()
    if period_type == ReviewTarget.PeriodType.WEEK:
        return _anchor_week(today)
    return _anchor_month(today)


def create_target(
    *,
    shop_id: int,
    org_id: int,
    period_type: str,
    period_start: datetime.date,
    target_count: int,
    created_by: User,
) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")

    # Verify the shop belongs to this org
    from apps.shops.models import Shop
    if not Shop.objects.filter(pk=shop_id, organisation_id=org_id).exists():
        raise ReviewTarget.DoesNotExist

    # Normalise period_start anchor
    if period_type == ReviewTarget.PeriodType.WEEK:
        period_start = _anchor_week(period_start)
    else:
        period_start = _anchor_month(period_start)

    # Reject past periods
    current_start = _current_period_start(period_type)
    if period_start < current_start:
        raise ValueError("Cannot set targets for past periods.")

    try:
        return ReviewTarget.objects.create(
            shop_id=shop_id,
            organisation_id=org_id,
            period_type=period_type,
            period_start=period_start,
            target_count=target_count,
            created_by=created_by,
        )
    except IntegrityError:
        raise ValueError("A target for this period already exists.") from None


def update_target(*, target_id: int, org_id: int, target_count: int) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.target_count = target_count
    target.save(update_fields=["target_count", "updated_at"])
    return target


def delete_target(*, target_id: int, org_id: int) -> None:
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.delete()
```

- [ ] **Step 4: Run service tests**

```bash
python -m pytest apps/shops/tests/test_target_services.py -v
```
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/shops/services/targets.py apps/shops/tests/test_target_services.py
git commit -m "feat(shops): add create/update/delete target services"
```

---

## Task 4: Serializers

**Files:**
- Create: `apps/shops/serializers/targets.py`

Note: `apps/shops/serializers.py` is a single file, not a package. Create a new file `apps/shops/serializers/targets.py` alongside it — but first check if `apps/shops/serializers/` is already a directory. If `serializers.py` is a flat file (it is, per the codebase), add the new serializers directly to `apps/shops/serializers.py` as additional classes.

- [ ] **Step 1: Append serializer classes to `apps/shops/serializers.py`**

Add these imports at the top of `apps/shops/serializers.py` (after existing imports):

```python
import datetime
from apps.shops.models import ReviewTarget
```

Then append these classes to the end of `apps/shops/serializers.py`:

```python
class ReviewTargetReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    period_type = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    target_count = serializers.IntegerField()
    received_count = serializers.IntegerField()
    pct = serializers.IntegerField()
    days_remaining = serializers.IntegerField()


class ReviewTargetCreateSerializer(serializers.Serializer):
    period_type = serializers.ChoiceField(choices=ReviewTarget.PeriodType.choices)
    period_start = serializers.DateField()
    target_count = serializers.IntegerField(min_value=1)

    def validate_target_count(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError("Target must be at least 1 review.")
        return value


class ReviewTargetUpdateSerializer(serializers.Serializer):
    target_count = serializers.IntegerField(min_value=1)
```

- [ ] **Step 2: Verify serializers import correctly**

```bash
python -c "from apps.shops.serializers import ReviewTargetReadSerializer, ReviewTargetCreateSerializer, ReviewTargetUpdateSerializer; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/shops/serializers.py
git commit -m "feat(shops): add ReviewTarget serializers"
```

---

## Task 5: API ViewSet + URL Wiring

**Files:**
- Modify: `apps/shops/views.py` (append `ReviewTargetViewSet`)
- Modify: `config/urls.py` (register new router entry)
- Create: `apps/shops/tests/test_target_views.py`

- [ ] **Step 1: Write the failing API tests**

```python
# apps/shops/tests/test_target_views.py
from __future__ import annotations

import datetime
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.organisations.tests.factories import OrganisationFactory
from apps.shops.models import ReviewTarget
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


@pytest.fixture
def org_admin_client(db):
    org = OrganisationFactory()
    admin = UserFactory(role="ORG_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=admin)
    return org, admin, client


@pytest.fixture
def staff_client(db):
    org = OrganisationFactory()
    staff = UserFactory(role="STAFF_ADMIN", organisation=org)
    client = APIClient()
    client.force_authenticate(user=staff)
    return org, staff, client


@pytest.fixture
def bypass_session_auth():
    with patch("apps.common.permissions.RequiresSessionAuth.has_permission", return_value=True):
        yield


@pytest.mark.django_db
class TestTargetList:
    def test_org_admin_can_list(self, org_admin_client):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        row = resp.data[0]
        assert "period_type" in row
        assert "received_count" in row
        assert "pct" in row
        assert "days_remaining" in row

    def test_staff_can_list_own_shop(self, staff_client):
        org, staff, client = staff_client
        shop = ShopFactory(organisation=org)
        # Staff has access to this shop (no StaffAccessScope set — defaults to all for this test)
        ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        shop = ShopFactory()
        client = APIClient()
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code in (401, 403)

    def test_cannot_list_other_orgs_shop(self, org_admin_client):
        org, admin, client = org_admin_client
        other_shop = ShopFactory()  # different org
        resp = client.get(f"/api/v1/shops/{other_shop.pk}/targets/")
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestTargetCreate:
    def test_org_admin_creates_target(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-01",
            "target_count": 200,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 201
        assert ReviewTarget.objects.filter(shop=shop, target_count=200).exists()

    def test_normalises_period_start(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-15",  # mid-month
            "target_count": 100,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 201
        t = ReviewTarget.objects.get(shop=shop)
        assert t.period_start == datetime.date(2026, 5, 1)

    def test_staff_cannot_create(self, staff_client, bypass_session_auth):
        org, staff, client = staff_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-05-01",
            "target_count": 50,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 403

    def test_past_period_returns_400(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {
            "period_type": "MONTH",
            "period_start": "2026-04-01",  # past
            "target_count": 100,
        }
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400

    def test_duplicate_returns_400(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(
            shop=shop, organisation=org,
            period_type=ReviewTarget.PeriodType.MONTH,
            period_start=datetime.date(2026, 5, 1),
        )
        payload = {"period_type": "MONTH", "period_start": "2026-05-01", "target_count": 999}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400

    def test_target_count_zero_returns_400(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "MONTH", "period_start": "2026-06-01", "target_count": 0}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTargetUpdate:
    def test_org_admin_updates_count(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org, target_count=100)
        resp = client.patch(
            f"/api/v1/shops/{shop.pk}/targets/{t.pk}/",
            {"target_count": 300},
            format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.target_count == 300

    def test_staff_cannot_update(self, staff_client, bypass_session_auth):
        org, staff, client = staff_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.patch(
            f"/api/v1/shops/{shop.pk}/targets/{t.pk}/",
            {"target_count": 999},
            format="json",
        )
        assert resp.status_code == 403

    def test_org_isolation(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        other_shop = ShopFactory()
        t = ReviewTargetFactory(shop=other_shop, organisation=other_shop.organisation)
        resp = client.patch(
            f"/api/v1/shops/{other_shop.pk}/targets/{t.pk}/",
            {"target_count": 999},
            format="json",
        )
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestTargetDelete:
    def test_org_admin_deletes(self, org_admin_client, bypass_session_auth):
        org, admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 204
        assert not ReviewTarget.objects.filter(pk=t.pk).exists()

    def test_staff_cannot_delete(self, staff_client, bypass_session_auth):
        org, staff, client = staff_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/shops/tests/test_target_views.py -v
```
Expected: connection refused or 404 — routes not registered yet.

- [ ] **Step 3: Add `ReviewTargetViewSet` to `apps/shops/views.py`**

Add these imports near the top of `apps/shops/views.py` (after existing imports):

```python
from apps.shops.selectors.targets import list_targets_for_shop
from apps.shops.serializers import (
    ReviewTargetCreateSerializer,
    ReviewTargetReadSerializer,
    ReviewTargetUpdateSerializer,
)
from apps.shops.services.targets import (
    create_target,
    delete_target,
    update_target,
)
from apps.shops.models import ReviewTarget
```

Append the new viewset class at the end of `apps/shops/views.py`:

```python
# ---------------------------------------------------------------------------
# ReviewTarget ViewSet — nested under /api/v1/shops/{shop_pk}/targets/
# ---------------------------------------------------------------------------


class ReviewTargetViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    queryset = ReviewTarget.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]  # noqa: RUF012

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "partial_update", "update", "destroy"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return [IsOrgScoped()]

    def _get_shop_id(self) -> int:
        return int(self.kwargs["shop_pk"])

    def _get_org_id(self) -> int:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise drf_serializers.ValidationError({"detail": ["Organisation not found."]})
        return user.organisation_id  # type: ignore[return-value]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        shop_id = self._get_shop_id()
        org_id = self._get_org_id()
        results = list_targets_for_shop(shop_id=shop_id, org_id=org_id)
        return Response(ReviewTargetReadSerializer(results, many=True).data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReviewTargetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not isinstance(user, User):
            raise drf_serializers.ValidationError({"detail": ["Authentication required."]})
        try:
            target = create_target(
                shop_id=self._get_shop_id(),
                org_id=self._get_org_id(),
                period_type=serializer.validated_data["period_type"],
                period_start=serializer.validated_data["period_start"],
                target_count=serializer.validated_data["target_count"],
                created_by=user,
            )
        except ValueError as exc:
            raise drf_serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        org_id = self._get_org_id()
        result = list_targets_for_shop(shop_id=self._get_shop_id(), org_id=org_id)
        row = next((r for r in result if r["id"] == target.pk), None)
        return Response(ReviewTargetReadSerializer(row).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReviewTargetUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            update_target(
                target_id=int(kwargs["pk"]),
                org_id=self._get_org_id(),
                target_count=serializer.validated_data["target_count"],
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            raise drf_serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        result = list_targets_for_shop(shop_id=self._get_shop_id(), org_id=self._get_org_id())
        row = next((r for r in result if r["id"] == int(kwargs["pk"])), None)
        return Response(ReviewTargetReadSerializer(row).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            delete_target(target_id=int(kwargs["pk"]), org_id=self._get_org_id())
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Register nested routes in `config/urls.py`**

Add this import at the top of `config/urls.py` (after existing shop imports):

```python
from apps.shops.views import ReviewTargetViewSet
```

Register the nested router. The nested route pattern uses a custom URL. After the existing `router.register(r"api/v1/shops", ShopViewSet, basename="shop")` line, add:

```python
router.register(
    r"api/v1/shops/(?P<shop_pk>[^/.]+)/targets",
    ReviewTargetViewSet,
    basename="shop-target",
)
```

- [ ] **Step 5: Run API tests**

```bash
python -m pytest apps/shops/tests/test_target_views.py -v
```
Expected: All 15 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/shops/views.py config/urls.py apps/shops/tests/test_target_views.py
git commit -m "feat(shops): add ReviewTargetViewSet and nested API routes"
```

---

## Task 6: Frontend — Types, API, Hook

**Files:**
- Modify: `frontend/src/widgets/shop-management/types.ts` (append `TargetRow`)
- Create: `frontend/src/widgets/shop-management/targetsApi.ts`
- Create: `frontend/src/widgets/shop-management/useTargets.ts`

- [ ] **Step 1: Add `TargetRow` type to `frontend/src/widgets/shop-management/types.ts`**

Append to the end of `types.ts`:

```typescript
export interface TargetRow {
  id: number;
  period_type: "MONTH" | "WEEK";
  period_start: string; // ISO date string e.g. "2026-05-01"
  period_end: string;   // ISO date string
  target_count: number;
  received_count: number;
  pct: number;
  days_remaining: number;
}

export interface TargetCreatePayload {
  period_type: "MONTH" | "WEEK";
  period_start: string;
  target_count: number;
}

export interface TargetUpdatePayload {
  target_count: number;
}
```

- [ ] **Step 2: Create `frontend/src/widgets/shop-management/targetsApi.ts`**

```typescript
import type { TargetCreatePayload, TargetRow, TargetUpdatePayload } from "./types";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function headers(method: string): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (method !== "GET" && method !== "HEAD") {
    h["X-CSRFToken"] = getCsrfToken();
  }
  return h;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(`API error ${status}`);
  }
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new ApiError(resp.status, data);
  }
  if (resp.status === 204) return null as T;
  return resp.json() as Promise<T>;
}

export async function listTargets(shopId: number): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return handle<TargetRow[]>(resp);
}

export async function createTarget(shopId: number, payload: TargetCreatePayload): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function patchTarget(
  shopId: number,
  targetId: number,
  payload: TargetUpdatePayload,
): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function deleteTarget(shopId: number, targetId: number): Promise<void> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  return handle<void>(resp);
}
```

- [ ] **Step 3: Create `frontend/src/widgets/shop-management/useTargets.ts`**

```typescript
import { useCallback, useState } from "react";
import { createTarget, deleteTarget, listTargets, patchTarget } from "./targetsApi";
import type { TargetCreatePayload, TargetRow, TargetUpdatePayload } from "./types";

interface UseTargetsState {
  rows: TargetRow[];
  loading: boolean;
  error: string | null;
}

export function useTargets(shopId: number | null) {
  const [state, setState] = useState<UseTargetsState>({
    rows: [],
    loading: false,
    error: null,
  });

  const load = useCallback(async () => {
    if (shopId === null) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const rows = await listTargets(shopId);
      setState({ rows, loading: false, error: null });
    } catch {
      setState((s) => ({ ...s, loading: false, error: "Failed to load targets." }));
    }
  }, [shopId]);

  const addTarget = useCallback(
    async (payload: TargetCreatePayload): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        const newRow = await createTarget(shopId, payload);
        setState((s) => ({ ...s, rows: [...s.rows, newRow] }));
        // Re-fetch for correct ordering
        const rows = await listTargets(shopId);
        setState((s) => ({ ...s, rows }));
        return null;
      } catch (err: unknown) {
        if (err && typeof err === "object" && "data" in err) {
          const data = (err as { data: unknown }).data;
          if (data && typeof data === "object" && "non_field_errors" in data) {
            const nfe = (data as { non_field_errors: string[] }).non_field_errors;
            return nfe[0] ?? "Failed to save target.";
          }
        }
        return "Failed to save target.";
      }
    },
    [shopId],
  );

  const editTarget = useCallback(
    async (targetId: number, payload: TargetUpdatePayload): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        const updated = await patchTarget(shopId, targetId, payload);
        setState((s) => ({
          ...s,
          rows: s.rows.map((r) => (r.id === targetId ? updated : r)),
        }));
        return null;
      } catch {
        return "Failed to update target.";
      }
    },
    [shopId],
  );

  const removeTarget = useCallback(
    async (targetId: number): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        await deleteTarget(shopId, targetId);
        setState((s) => ({ ...s, rows: s.rows.filter((r) => r.id !== targetId) }));
        return null;
      } catch {
        return "Failed to delete target.";
      }
    },
    [shopId],
  );

  return {
    rows: state.rows,
    loading: state.loading,
    error: state.error,
    load,
    addTarget,
    editTarget,
    removeTarget,
  };
}
```

- [ ] **Step 4: Type-check**

```bash
cd /Users/renjith/Documents/Accounts/review-master/frontend
npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/widgets/shop-management/types.ts \
        frontend/src/widgets/shop-management/targetsApi.ts \
        frontend/src/widgets/shop-management/useTargets.ts
git commit -m "feat(shops): add TargetRow types, targets API client, useTargets hook"
```

---

## Task 7: Frontend — `TargetsTab.tsx` + `SetTargetModal.tsx`

**Files:**
- Create: `frontend/src/widgets/shop-management/TargetsTab.tsx`
- Create: `frontend/src/widgets/shop-management/SetTargetModal.tsx`

- [ ] **Step 1: Create `frontend/src/widgets/shop-management/TargetsTab.tsx`**

```tsx
import { useEffect, useState } from "react";
import type { TargetRow } from "./types";
import type { UseTargets } from "./useTargets";

interface Props {
  shopId: number;
  isOrgAdmin: boolean;
  targets: ReturnType<typeof import("./useTargets").useTargets>;
  onAddTarget: () => void;
}

function progressColor(pct: number): string {
  if (pct >= 70) return "#16a34a"; // green
  if (pct >= 40) return "#d97706"; // amber
  return "#dc2626"; // red
}

function formatPeriodLabel(row: TargetRow): string {
  if (row.period_type === "MONTH") {
    const d = new Date(row.period_start + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }
  const start = new Date(row.period_start + "T00:00:00");
  const end = new Date(row.period_end + "T00:00:00");
  const fmt = (d: Date) =>
    d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `Week of ${fmt(start)}–${fmt(end)}`;
}

function isFuture(row: TargetRow): boolean {
  return new Date(row.period_start + "T00:00:00") > new Date();
}

interface EditRowProps {
  row: TargetRow;
  onSave: (count: number) => void;
  onCancel: () => void;
}

function EditRow({ row, onSave, onCancel }: EditRowProps) {
  const [value, setValue] = useState(String(row.target_count));

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        min="1"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSave(parseInt(value, 10));
          if (e.key === "Escape") onCancel();
        }}
        className="w-24 border border-line rounded px-2 py-1 text-[13px] font-semibold"
        autoFocus
      />
      <span className="text-[11.5px] text-subtle">reviews</span>
      <button
        type="button"
        onClick={() => onSave(parseInt(value, 10))}
        className="text-[11.5px] text-green-700 font-medium hover:underline"
      >
        Save
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-[11.5px] text-subtle hover:underline"
      >
        Cancel
      </button>
    </div>
  );
}

export function TargetsTab({ shopId, isOrgAdmin, targets, onAddTarget }: Props) {
  const { rows, loading, error, load, editTarget, removeTarget } = targets;
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <p className="text-[13px] text-subtle py-4 text-center">Loading targets…</p>;
  }

  if (error) {
    return (
      <div className="py-4 text-center">
        <p className="text-[13px] text-red-600 mb-2">{error}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="text-[12px] text-ink underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="py-8 text-center">
        {isOrgAdmin ? (
          <>
            <p className="text-[13px] text-subtle mb-3">No targets set for this shop.</p>
            <button
              type="button"
              onClick={onAddTarget}
              className="px-4 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13px] font-semibold hover:bg-yellow-hover"
            >
              Set your first target →
            </button>
          </>
        ) : (
          <p className="text-[13px] text-subtle">No targets set.</p>
        )}
      </div>
    );
  }

  const handleSave = async (targetId: number, count: number) => {
    setActionError(null);
    const err = await editTarget(targetId, { target_count: count });
    if (err) {
      setActionError(err);
    } else {
      setEditingId(null);
    }
  };

  const handleDelete = async (targetId: number) => {
    setActionError(null);
    const err = await removeTarget(targetId);
    if (err) setActionError(err);
    setDeleteConfirmId(null);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <span className="text-[12px] text-subtle">Current &amp; upcoming targets</span>
        {isOrgAdmin && (
          <button
            type="button"
            onClick={onAddTarget}
            className="px-3 py-1.5 bg-yellow text-black border border-yellow-hover rounded-md text-[12px] font-semibold hover:bg-yellow-hover"
          >
            + Set Target
          </button>
        )}
      </div>

      {actionError && (
        <p className="text-[12px] text-red-600 mb-2">{actionError}</p>
      )}

      <div className="flex flex-col gap-2">
        {rows.map((row) => {
          const future = isFuture(row);
          const color = progressColor(row.pct);
          return (
            <div
              key={row.id}
              className={`rounded-lg p-3 ${future ? "border border-dashed border-line bg-surface-soft" : "border border-line"}`}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="text-[12.5px] font-semibold text-ink">
                    {formatPeriodLabel(row)}
                  </div>
                  <div className="text-[10.5px] text-subtle mt-0.5">
                    {row.period_type === "MONTH" ? "Monthly" : "Weekly"} ·{" "}
                    {future
                      ? `starts in ${row.days_remaining} days`
                      : `${row.days_remaining} days left`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {editingId === row.id ? (
                    <EditRow
                      row={row}
                      onSave={(count) => void handleSave(row.id, count)}
                      onCancel={() => setEditingId(null)}
                    />
                  ) : (
                    <>
                      {future ? (
                        <span className="text-[11px] font-medium text-subtle">
                          Target: {row.target_count}
                        </span>
                      ) : (
                        <span className="text-[11px] font-semibold text-ink">
                          {row.received_count} / {row.target_count}
                        </span>
                      )}
                      {isOrgAdmin && (
                        <>
                          <button
                            type="button"
                            onClick={() => setEditingId(row.id)}
                            className="text-subtle hover:text-ink text-[12px] p-0.5"
                            aria-label="Edit target"
                          >
                            ✎
                          </button>
                          {deleteConfirmId === row.id ? (
                            <span className="text-[11px] flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => void handleDelete(row.id)}
                                className="text-red-600 font-medium hover:underline"
                              >
                                Confirm
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeleteConfirmId(null)}
                                className="text-subtle hover:underline"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setDeleteConfirmId(row.id)}
                              className="text-red-400 hover:text-red-600 text-[12px] p-0.5"
                              aria-label="Delete target"
                            >
                              ✕
                            </button>
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>

              {!future && (
                <>
                  <div className="bg-gray-100 rounded h-1.5 overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{ width: `${row.pct}%`, backgroundColor: color }}
                    />
                  </div>
                  <div className="flex justify-between mt-1.5">
                    <span className="text-[10.5px] font-semibold" style={{ color }}>
                      {row.pct}% complete
                    </span>
                    <span className="text-[10.5px] text-subtle">
                      {Math.max(0, row.target_count - row.received_count)} more needed
                    </span>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/widgets/shop-management/SetTargetModal.tsx`**

```tsx
import { useState } from "react";
import { Modal } from "../modal/Modal";
import type { TargetCreatePayload, TargetRow } from "./types";

interface Props {
  open: boolean;
  shopId: number;
  existingTargets: TargetRow[];
  onSave: (payload: TargetCreatePayload) => Promise<string | null>;
  onClose: () => void;
}

function getMonthOptions(existing: TargetRow[]): { label: string; value: string }[] {
  const existingKeys = new Set(
    existing
      .filter((t) => t.period_type === "MONTH")
      .map((t) => t.period_start),
  );
  const options: { label: string; value: string }[] = [];
  const today = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const iso = d.toISOString().split("T")[0];
    if (existingKeys.has(iso)) continue;
    const label =
      d.toLocaleDateString(undefined, { month: "long", year: "numeric" }) +
      (i === 0 ? " (current)" : "");
    options.push({ label, value: iso });
  }
  return options;
}

function getWeekOptions(existing: TargetRow[]): { label: string; value: string }[] {
  const existingKeys = new Set(
    existing
      .filter((t) => t.period_type === "WEEK")
      .map((t) => t.period_start),
  );
  const options: { label: string; value: string }[] = [];
  const today = new Date();
  const dayOfWeek = today.getDay();
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const currentMonday = new Date(today);
  currentMonday.setDate(today.getDate() + mondayOffset);

  for (let i = 0; i < 52; i++) {
    const monday = new Date(currentMonday);
    monday.setDate(currentMonday.getDate() + i * 7);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    const iso = monday.toISOString().split("T")[0];
    if (existingKeys.has(iso)) continue;
    const fmt = (d: Date) =>
      d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const label = `${fmt(monday)} – ${fmt(sunday)}` + (i === 0 ? " (current)" : "");
    options.push({ label, value: iso });
  }
  return options;
}

export function SetTargetModal({ open, shopId: _shopId, existingTargets, onSave, onClose }: Props) {
  const [periodType, setPeriodType] = useState<"MONTH" | "WEEK">("MONTH");
  const [periodStart, setPeriodStart] = useState("");
  const [targetCount, setTargetCount] = useState("100");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const monthOptions = getMonthOptions(existingTargets);
  const weekOptions = getWeekOptions(existingTargets);
  const options = periodType === "MONTH" ? monthOptions : weekOptions;

  // Auto-select first option when period type changes
  const handlePeriodTypeChange = (pt: "MONTH" | "WEEK") => {
    setPeriodType(pt);
    const opts = pt === "MONTH" ? getMonthOptions(existingTargets) : getWeekOptions(existingTargets);
    setPeriodStart(opts[0]?.value ?? "");
    setError(null);
  };

  // Initialise selection on open
  if (!periodStart && options.length > 0) {
    setPeriodStart(options[0].value);
  }

  // Info note: current period with existing reviews
  const selectedTarget = existingTargets.find(
    (t) => t.period_type === periodType && t.period_start === periodStart,
  );
  const currentPeriodReceived = (() => {
    if (!periodStart) return null;
    const today = new Date().toISOString().split("T")[0];
    const opts = options.find((o) => o.value === periodStart);
    if (!opts) return null;
    // Find if the currently-selected slot is the current period
    const isCurrentPeriod = opts.label.includes("(current)");
    if (!isCurrentPeriod) return null;
    // Check if there's an existing partially-tracked target
    // (We show a note if they're creating a target for the current period that already has reviews —
    //  but this is a new target so received_count from existing won't apply here. We can't know
    //  without an API call. Skip info note on create form — it only applies when the period
    //  already has a target, which means it's already filtered out of the dropdown.)
    return null;
  })();

  const handleSave = async () => {
    if (!periodStart) {
      setError("Please select a period.");
      return;
    }
    const count = parseInt(targetCount, 10);
    if (isNaN(count) || count < 1) {
      setError("Target must be at least 1.");
      return;
    }
    setSaving(true);
    setError(null);
    const err = await onSave({ period_type: periodType, period_start: periodStart, target_count: count });
    setSaving(false);
    if (err) {
      setError(err);
    } else {
      onClose();
      // Reset form
      setPeriodType("MONTH");
      setPeriodStart("");
      setTargetCount("100");
    }
  };

  return (
    <Modal
      open={open}
      title="Set Review Target"
      size="sm"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || options.length === 0}
            className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Target"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Period type toggle */}
        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Period Type
          </div>
          <div className="flex gap-2">
            {(["MONTH", "WEEK"] as const).map((pt) => (
              <button
                key={pt}
                type="button"
                onClick={() => handlePeriodTypeChange(pt)}
                className={`flex-1 py-2 rounded-md text-[12.5px] font-semibold border transition-colors ${
                  periodType === pt
                    ? "border-yellow bg-yellow/10 text-ink"
                    : "border-line bg-white text-subtle hover:bg-line-soft"
                }`}
              >
                {pt === "MONTH" ? "Monthly" : "Weekly"}
              </button>
            ))}
          </div>
        </div>

        {/* Period selector */}
        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Period
          </div>
          {options.length === 0 ? (
            <p className="text-[12px] text-subtle italic">
              All {periodType === "MONTH" ? "monthly" : "weekly"} periods have targets set.
            </p>
          ) : (
            <select
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-full border border-line rounded-md px-3 py-2 text-[13px] text-ink bg-white"
            >
              {options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Target count */}
        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Review Target
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="1"
              value={targetCount}
              onChange={(e) => setTargetCount(e.target.value)}
              className="flex-1 border border-line rounded-md px-3 py-2 text-[13.5px] font-semibold"
            />
            <span className="text-[12px] text-subtle whitespace-nowrap">reviews</span>
          </div>
        </div>

        {error && (
          <p className="text-[12px] text-red-600">{error}</p>
        )}
      </div>
    </Modal>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd /Users/renjith/Documents/Accounts/review-master/frontend
npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/shop-management/TargetsTab.tsx \
        frontend/src/widgets/shop-management/SetTargetModal.tsx
git commit -m "feat(shops): add TargetsTab and SetTargetModal components"
```

---

## Task 8: Wire Tabs into `ShopDetailsModal`

**Files:**
- Modify: `frontend/src/widgets/shop-management/ShopDetailsModal.tsx`

- [ ] **Step 1: Update `ShopDetailsModal.tsx`**

Replace the entire file with the following (it preserves all existing details-tab content and adds the tab switcher + targets tab):

```tsx
import { useState } from "react";
import { Modal } from "../modal/Modal";
import { ConnectionStatusPill } from "./ConnectionStatusPill";
import { SetTargetModal } from "./SetTargetModal";
import { TargetsTab } from "./TargetsTab";
import { useTargets } from "./useTargets";
import type { ShopRow } from "./types";

interface Props {
  open: boolean;
  shop: ShopRow | null;
  isOrgAdmin: boolean;
  onClose: () => void;
  onEdit: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onReconnect: () => void;
}

const dtCls = "text-[11.5px] font-semibold text-subtle tracking-[0.05em] uppercase mb-0.5";
const ddCls = "text-[13.5px] text-ink";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className={dtCls}>{label}</dt>
      <dd className={ddCls}>{children}</dd>
    </div>
  );
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

type TabId = "details" | "targets";

export function ShopDetailsModal({
  open,
  shop,
  isOrgAdmin,
  onClose,
  onEdit,
  onActivate,
  onDeactivate,
  onReconnect,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("details");
  const [showSetTarget, setShowSetTarget] = useState(false);

  const showReconnect =
    shop?.connection_method === "GOOGLE_OAUTH" &&
    (shop.connection_status === "ERROR" || shop.connection_status === "EXPIRED");

  const targets = useTargets(shop?.id ?? null);

  const handleModalClose = () => {
    setActiveTab("details");
    onClose();
  };

  const tabs: { id: TabId; label: string }[] = [
    { id: "details", label: "Details" },
    { id: "targets", label: "Review Targets" },
  ];

  return (
    <>
      <Modal
        open={open}
        title="Shop Details"
        size="lg"
        onClose={handleModalClose}
        footer={
          <>
            {showReconnect && (
              <button
                type="button"
                onClick={onReconnect}
                className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
              >
                Reconnect Google
              </button>
            )}
            <button
              type="button"
              onClick={onEdit}
              className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            >
              Edit
            </button>
            {shop?.is_active ? (
              <button
                type="button"
                onClick={onDeactivate}
                className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              >
                Deactivate
              </button>
            ) : (
              <button
                type="button"
                onClick={onActivate}
                className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              >
                Activate
              </button>
            )}
            <button
              type="button"
              onClick={handleModalClose}
              className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
            >
              Close
            </button>
          </>
        }
      >
        {/* Tab switcher */}
        <div className="flex border-b border-line mb-4 -mt-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-[12.5px] font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-yellow text-ink font-semibold"
                  : "border-transparent text-subtle hover:text-ink"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {shop ? (
          activeTab === "details" ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
              <Row label="Shop Name">{shop.name}</Row>
              <Row label="Phone">{shop.phone || "—"}</Row>
              <Row label="Region">
                {shop.region_region_id ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
                      style={{ backgroundColor: "#F3F4F6", color: "#374151" }}
                    >
                      {shop.region_region_id}
                    </span>
                    {shop.region_name}
                  </span>
                ) : (
                  "—"
                )}
              </Row>
              <Row label="Status">
                <span
                  className="inline-flex items-center rounded-full px-2 py-[3px] text-[12px] font-medium"
                  style={
                    shop.is_active
                      ? { backgroundColor: "#F0FDF4", color: "#16A34A" }
                      : { backgroundColor: "#F9FAFB", color: "#6B7280" }
                  }
                >
                  {shop.is_active ? "Active" : "Inactive"}
                </span>
              </Row>
              <Row label="Street Address">{shop.street_address || "—"}</Row>
              <Row label="Place ID">
                <code className="font-mono text-[12.5px]">{shop.place_id || "—"}</code>
              </Row>
              <Row label="Connection Method">
                {shop.connection_method === "GOOGLE_OAUTH" ? "Google OAuth" : "Not connected"}
              </Row>
              <Row label="Connection Status">
                <ConnectionStatusPill
                  method={shop.connection_method}
                  status={shop.connection_status}
                />
              </Row>
              <Row label="Created">{formatDate(shop.created_at)}</Row>
              <Row label="Updated">{formatDate(shop.updated_at)}</Row>
            </dl>
          ) : (
            <TargetsTab
              shopId={shop.id}
              isOrgAdmin={isOrgAdmin}
              targets={targets}
              onAddTarget={() => setShowSetTarget(true)}
            />
          )
        ) : (
          <p className="text-[13.5px] text-muted">No shop selected.</p>
        )}
      </Modal>

      {shop && (
        <SetTargetModal
          open={showSetTarget}
          shopId={shop.id}
          existingTargets={targets.rows}
          onSave={targets.addTarget}
          onClose={() => setShowSetTarget(false)}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: Update all usages of `ShopDetailsModal` to pass `isOrgAdmin`**

Find where `ShopDetailsModal` is rendered (in `ShopModals.tsx` or similar):

```bash
grep -rn "ShopDetailsModal" /Users/renjith/Documents/Accounts/review-master/frontend/src/ --include="*.tsx"
```

In the file that renders `<ShopDetailsModal>`, add the `isOrgAdmin` prop. The value comes from the page-level user role. Check how `ShopModals.tsx` receives its props and pass through:

```tsx
// In ShopModals.tsx (or wherever ShopDetailsModal is rendered):
// Add isOrgAdmin to Props interface if not already present:
// isOrgAdmin: boolean;

// Then pass it through:
<ShopDetailsModal
  {...existingProps}
  isOrgAdmin={isOrgAdmin}
/>
```

- [ ] **Step 3: Find the `isOrgAdmin` source and pass it down**

```bash
grep -rn "isOrgAdmin\|is_org_admin\|ORG_ADMIN\|role" /Users/renjith/Documents/Accounts/review-master/frontend/src/widgets/shop-management/ --include="*.tsx" | head -20
```

The role is typically available from the Django template context injected into the React entrypoint. Check `ShopModals.tsx` and the entrypoint that mounts it to trace how role is made available. Pass `isOrgAdmin` as a boolean prop from the entrypoint down to `ShopDetailsModal`.

- [ ] **Step 4: Type-check**

```bash
cd /Users/renjith/Documents/Accounts/review-master/frontend
npx tsc --noEmit
```
Expected: 0 errors.

- [ ] **Step 5: Build**

```bash
npm run build
```
Expected: build completes with 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/widgets/shop-management/ShopDetailsModal.tsx \
        frontend/src/widgets/shop-management/ShopModals.tsx
git commit -m "feat(shops): integrate TargetsTab into ShopDetailsModal with tab switcher"
```

---

## Task 9: Full Test Run + Spec Self-Check

- [ ] **Step 1: Run full backend test suite**

```bash
cd /Users/renjith/Documents/Accounts/review-master
python -m pytest apps/shops/tests/ -v --tb=short
```
Expected: All tests PASS. Fix any failures before proceeding.

- [ ] **Step 2: Run pre-commit hooks**

```bash
pre-commit run --all-files
```
Expected: all hooks pass (ruff, mypy, djhtml, etc).

- [ ] **Step 3: Check for missing migrations**

```bash
python manage.py makemigrations --check --dry-run
```
Expected: "No changes detected."

- [ ] **Step 4: Final commit with any fixups**

```bash
git add -p  # review any remaining changes
git commit -m "chore(shops): pre-commit fixups for review target feature"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|---|---|
| `ReviewTarget` model with unique constraint | Task 1 |
| `period_start` normalised to Monday/1st of month | Task 3 (services) |
| Reject past periods → 400 | Task 3 (services) + Task 5 (views) |
| Reject duplicate period → 400 | Task 3 (services) + Task 5 (views) |
| Reject `target_count < 1` → 400 | Task 3 (services) + Task 5 (views) |
| `GET /api/v1/shops/{id}/targets/` with live progress | Task 2 (selector) + Task 5 (views) |
| `POST` Org Admin only | Task 5 (views) |
| `PATCH` Org Admin only, `target_count` only | Task 5 (views) |
| `DELETE` Org Admin only | Task 5 (views) |
| Staff read-only (GET works, POST/PATCH/DELETE → 403) | Task 5 (views) |
| Org scoping (org A cannot read org B) | Task 2 (selector) + Task 5 (views) |
| `received_count` excludes soft-deleted reviews | Task 2 (selector) |
| `pct` capped at 100 | Task 2 (selector) |
| `days_remaining` min 0 | Task 2 (selector) |
| `period_end` correct for WEEK (Sunday) and MONTH (last day) | Task 2 (selector) |
| Frontend tab in ShopDetailsModal | Task 8 |
| Progress bars with correct colour (green ≥ 70%, amber 40–69%, red < 40%) | Task 7 (TargetsTab) |
| Future targets shown with dashed border, no progress bar | Task 7 (TargetsTab) |
| Edit inline (input on edit button click) | Task 7 (TargetsTab) |
| Delete with confirmation | Task 7 (TargetsTab) |
| Staff: no edit/delete buttons | Task 7 (TargetsTab — `isOrgAdmin` prop) |
| `SetTargetModal` excludes already-set periods from dropdown | Task 7 (SetTargetModal) |
| Period type toggle Monthly/Weekly | Task 7 (SetTargetModal) |
| Empty state CTA for Org Admin / plain text for Staff | Task 7 (TargetsTab) |
| API error with retry button | Task 7 (TargetsTab) |
