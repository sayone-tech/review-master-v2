# Recurring Review Targets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-period `ReviewTarget` rows with a recurring model (max 2 per shop — one weekly, one monthly), computed at query time against the current period, served from a dedicated per-shop page at `/admin/org/shops/<id>/targets/`.

**Architecture:** Drop `period_start` from `ReviewTarget` (unique on `(shop, period_type)` instead); `set_target` upserts via `update_or_create`; `list_targets_for_shop` selector computes current-period progress at query time; a new Django template view at `/admin/org/shops/<id>/targets/` mounts a React widget; the shop `...` menu navigates there with `window.location.href`. Old modal/tab files are deleted.

**Tech Stack:** Django 6, DRF, pytest + factory-boy, React 18, TypeScript, Tailwind CSS, Vite.

---

## File Map

**Create:**
- `apps/shops/migrations/0007_recurring_review_targets.py` — data wipe + schema migration
- `frontend/src/widgets/shop-targets/types.ts` — TargetRow, SetTargetPayload
- `frontend/src/widgets/shop-targets/api.ts` — listTargets, setTarget, deleteTarget
- `frontend/src/widgets/shop-targets/ShopTargetsWidget.tsx` — main page widget
- `frontend/src/entrypoints/shop-targets.tsx` — React root mount
- `templates/org/shop_targets.html` — Django template shell

**Modify:**
- `apps/shops/models.py` — remove `period_start`, update Meta
- `apps/shops/services/targets.py` — replace create/update with `set_target`
- `apps/shops/selectors/targets.py` — rewrite for current-period progress + `period_label`
- `apps/shops/serializers.py` — new read serializer (no period_start/end), new write serializer
- `apps/shops/views.py` — simplify `ReviewTargetViewSet` (no PATCH); add `shop_targets_view`
- `apps/shops/urls.py` — add `/admin/org/shops/<id>/targets/` URL
- `apps/shops/tests/factories.py` — remove `period_start` from `ReviewTargetFactory`
- `apps/shops/tests/test_target_services.py` — rewrite for `set_target`
- `apps/shops/tests/test_target_selectors.py` — rewrite for current-period selector
- `apps/shops/tests/test_target_views.py` — rewrite (no PATCH, POST is upsert)
- `frontend/vite.config.ts` — add `shop-targets` entrypoint
- `frontend/src/widgets/shop-management/ShopTable.tsx` — targets action → `window.location.href`
- `frontend/src/widgets/shop-management/ShopModals.tsx` — remove `detailsInitialTab` + `shop:open-targets`
- `frontend/src/widgets/shop-management/ShopDetailsModal.tsx` — remove Targets tab, SetTargetModal, useTargets

**Delete:**
- `frontend/src/widgets/shop-management/SetTargetModal.tsx`
- `frontend/src/widgets/shop-management/TargetsTab.tsx`
- `frontend/src/widgets/shop-management/targetsApi.ts`
- `frontend/src/widgets/shop-management/useTargets.ts`
- `frontend/src/widgets/action-items/ShopTargetsModal.tsx`

---

## Task 1: Migration — wipe data + update schema

**Files:**
- Create: `apps/shops/migrations/0007_recurring_review_targets.py`

- [ ] **Step 1: Write the migration**

```python
# apps/shops/migrations/0007_recurring_review_targets.py
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0006_add_review_target"),
    ]

    operations = [
        # 1. Wipe all existing per-period rows (incompatible with recurring design)
        migrations.RunSQL(
            "DELETE FROM shops_reviewtarget;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # 2. Drop old three-field unique constraint
        migrations.RemoveConstraint(
            model_name="reviewtarget",
            name="target_unique_per_shop_period",
        ),
        # 3. Drop old index
        migrations.RemoveIndex(
            model_name="reviewtarget",
            name="target_org_shop_period_idx",
        ),
        # 4. Drop period_start column
        migrations.RemoveField(
            model_name="reviewtarget",
            name="period_start",
        ),
        # 5. Add new two-field unique constraint
        migrations.AddConstraint(
            model_name="reviewtarget",
            constraint=models.UniqueConstraint(
                fields=["shop", "period_type"],
                name="target_unique_per_shop_period_type",
            ),
        ),
        # 6. Add new index (without period_start)
        migrations.AddIndex(
            model_name="reviewtarget",
            index=models.Index(
                fields=["organisation", "shop", "period_type"],
                name="target_org_shop_period_type_idx",
            ),
        ),
        # 7. Update ordering (remove period_start from ordering)
        migrations.AlterModelOptions(
            name="reviewtarget",
            options={
                "db_table": "shops_reviewtarget",
                "ordering": ["period_type"],
            },
        ),
    ]
```

- [ ] **Step 2: Verify migration is valid**

```bash
python manage.py migrate --run-syncdb 2>&1 | head -5
# Expected: no errors; or run:
python manage.py showmigrations shops
# Expected: shows 0007_recurring_review_targets as [ ] (pending)
```

- [ ] **Step 3: Apply the migration**

```bash
python manage.py migrate shops
```

Expected: `Applying shops.0007_recurring_review_targets... OK`

- [ ] **Step 4: Commit**

```bash
git add apps/shops/migrations/0007_recurring_review_targets.py
git commit -m "feat(shops): migration — wipe per-period targets, drop period_start, new unique constraint"
```

---

## Task 2: Update model

**Files:**
- Modify: `apps/shops/models.py`

- [ ] **Step 1: Write the failing migration check (proves model matches DB)**

```bash
python manage.py makemigrations --check --dry-run
# Expected: "No changes detected"
# If it says changes detected, the model is out of sync — proceed to Step 2 first.
```

- [ ] **Step 2: Update ReviewTarget model**

In `apps/shops/models.py`, replace the `ReviewTarget` class with:

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
        related_name="review_targets",
    )
    period_type = models.CharField(
        max_length=5,
        choices=PeriodType.choices,
        db_index=True,
    )
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
        ordering: ClassVar[list[str]] = ["period_type"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["shop", "period_type"],
                name="target_unique_per_shop_period_type",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "shop", "period_type"],
                name="target_org_shop_period_type_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"ReviewTarget({self.shop_id} {self.period_type})"
```

- [ ] **Step 3: Verify no new migration is needed**

```bash
python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`

- [ ] **Step 4: Commit**

```bash
git add apps/shops/models.py
git commit -m "feat(shops): remove period_start from ReviewTarget model"
```

---

## Task 3: Update factory

**Files:**
- Modify: `apps/shops/tests/factories.py`

- [ ] **Step 1: Update ReviewTargetFactory**

Replace the `ReviewTargetFactory` class in `apps/shops/tests/factories.py`:

```python
class ReviewTargetFactory(DjangoModelFactory):
    class Meta:
        model = ReviewTarget

    organisation = factory.LazyAttribute(lambda o: o.shop.organisation)
    shop = factory.SubFactory("apps.shops.tests.factories.ShopFactory")
    period_type = ReviewTarget.PeriodType.MONTH
    target_count = 100
    created_by = None
```

Remove the `period_start` field and the `import datetime` line if it's only used there. (Keep `import datetime` if `datetime` is used elsewhere in the file — check first.)

- [ ] **Step 2: Run existing tests to confirm factory works**

```bash
pytest apps/shops/tests/test_models.py apps/shops/tests/test_services.py -v
```

Expected: all pass (or already-deleted tests are gone)

- [ ] **Step 3: Commit**

```bash
git add apps/shops/tests/factories.py
git commit -m "feat(shops): remove period_start from ReviewTargetFactory"
```

---

## Task 4: Rewrite service — `set_target`

**Files:**
- Modify: `apps/shops/services/targets.py`
- Test: `apps/shops/tests/test_target_services.py`

- [ ] **Step 1: Write failing tests**

Replace the entire contents of `apps/shops/tests/test_target_services.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest apps/shops/tests/test_target_services.py -v
```

Expected: ImportError or `AttributeError: module has no attribute 'set_target'`

- [ ] **Step 3: Rewrite `apps/shops/services/targets.py`**

```python
from __future__ import annotations

from apps.accounts.models import User
from apps.shops.models import ReviewTarget


def set_target(
    *,
    shop_id: int,
    org_id: int,
    period_type: str,
    target_count: int,
    created_by: User,
) -> ReviewTarget:
    if target_count < 1:
        raise ValueError("Target must be at least 1 review.")

    from apps.shops.models import Shop

    if not Shop.objects.filter(pk=shop_id, organisation_id=org_id).exists():
        raise ReviewTarget.DoesNotExist

    target, _ = ReviewTarget.objects.update_or_create(
        shop_id=shop_id,
        organisation_id=org_id,
        period_type=period_type,
        defaults={"target_count": target_count, "created_by": created_by},
    )
    return target


def delete_target(*, target_id: int, org_id: int) -> None:
    target = ReviewTarget.objects.get(pk=target_id, organisation_id=org_id)
    target.delete()
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
pytest apps/shops/tests/test_target_services.py -v
```

Expected: 7 tests pass

- [ ] **Step 5: Commit**

```bash
git add apps/shops/services/targets.py apps/shops/tests/test_target_services.py
git commit -m "feat(shops): rewrite set_target as upsert, remove create_target/update_target"
```

---

## Task 5: Rewrite selector — current-period progress

**Files:**
- Modify: `apps/shops/selectors/targets.py`
- Test: `apps/shops/tests/test_target_selectors.py`

- [ ] **Step 1: Write failing tests**

Replace the entire contents of `apps/shops/tests/test_target_selectors.py`:

```python
from __future__ import annotations

import datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.models import ReviewTarget
from apps.shops.selectors.targets import list_targets_for_shop
from apps.shops.tests.factories import ReviewTargetFactory, ShopFactory


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _today() -> datetime.date:
    return datetime.date.today()


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
            target_count=200,
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert len(result) == 1
        row = result[0]
        assert row["id"] == t.pk
        assert row["period_type"] == "MONTH"
        assert row["target_count"] == 200
        assert row["received_count"] == 0
        assert row["pct"] == 0
        assert isinstance(row["days_remaining"], int)
        assert row["days_remaining"] >= 0
        assert isinstance(row["period_label"], str)
        assert len(row["period_label"]) > 0

    def test_received_count_counts_reviews_in_current_month(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.MONTH,
            target_count=10,
        )
        today = _today()
        # 3 reviews inside the current month
        for _ in range(3):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
                ),
            )
        # 1 review in the previous month — should be excluded
        prev_month = (today.replace(day=1) - datetime.timedelta(days=1))
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                prev_month.year, prev_month.month, prev_month.day, 12, 0, tzinfo=datetime.UTC
            ),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 3
        assert result[0]["pct"] == 30

    def test_received_count_counts_reviews_in_current_week(self):
        shop = ShopFactory()
        ReviewTargetFactory(
            shop=shop,
            period_type=ReviewTarget.PeriodType.WEEK,
            target_count=10,
        )
        today = _today()
        week_start = today - datetime.timedelta(days=today.weekday())
        # 2 reviews inside the current week
        for _ in range(2):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    week_start.year, week_start.month, week_start.day, 12, 0,
                    tzinfo=datetime.UTC,
                ),
            )
        # 1 review 7 days before Monday — previous week, excluded
        prev_week_day = week_start - datetime.timedelta(days=1)
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                prev_week_day.year, prev_week_day.month, prev_week_day.day, 12, 0,
                tzinfo=datetime.UTC,
            ),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 2

    def test_soft_deleted_reviews_excluded(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=10)
        today = _today()
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
            ),
        )
        ReviewFactory(
            shop=shop,
            organisation=shop.organisation,
            review_create_time=datetime.datetime(
                today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
            ),
            deleted_at=_now_utc(),
        )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["received_count"] == 1

    def test_pct_capped_at_100(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=2)
        today = _today()
        for _ in range(5):
            ReviewFactory(
                shop=shop,
                organisation=shop.organisation,
                review_create_time=datetime.datetime(
                    today.year, today.month, today.day, 12, 0, tzinfo=datetime.UTC
                ),
            )
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert result[0]["pct"] == 100

    def test_month_period_label_format(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=10)
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        # e.g. "May 2026"
        import re
        assert re.match(r"^[A-Z][a-z]+ \d{4}$", result[0]["period_label"])

    def test_week_period_label_contains_week_of(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.WEEK, target_count=5)
        result = list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        assert "Week of" in result[0]["period_label"]

    def test_org_isolation(self):
        org_a = OrganisationFactory()
        shop_a = ShopFactory(organisation=org_a)
        org_b = OrganisationFactory()
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)
        result = list_targets_for_shop(shop_id=shop_a.pk, org_id=org_a.pk)
        assert result == []

    def test_cross_tenant_cannot_see_other_org_targets(self):
        org_a = OrganisationFactory()
        org_b = OrganisationFactory()
        shop_b = ShopFactory(organisation=org_b)
        ReviewTargetFactory(shop=shop_b)
        result = list_targets_for_shop(shop_id=shop_b.pk, org_id=org_a.pk)
        assert result == []

    def test_query_count_fixed_for_two_targets(self):
        shop = ShopFactory()
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.WEEK, target_count=10)
        ReviewTargetFactory(shop=shop, period_type=ReviewTarget.PeriodType.MONTH, target_count=40)
        with CaptureQueriesContext(connection) as ctx:
            list_targets_for_shop(shop_id=shop.pk, org_id=shop.organisation_id)
        # 1 query for targets + 1 for reviews = 2
        assert len(ctx.captured_queries) <= 3
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest apps/shops/tests/test_target_selectors.py -v
```

Expected: many failures (old selector has wrong signature / fields)

- [ ] **Step 3: Rewrite `apps/shops/selectors/targets.py`**

```python
from __future__ import annotations

import datetime
from math import floor

from apps.reviews.models import Review
from apps.shops.models import ReviewTarget


def _current_period_bounds(period_type: str) -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    if period_type == ReviewTarget.PeriodType.WEEK:
        start = today - datetime.timedelta(days=today.weekday())  # Monday
        end = start + datetime.timedelta(days=6)  # Sunday
        return start, end
    # MONTH
    start = today.replace(day=1)
    if today.month == 12:
        end = datetime.date(today.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end = datetime.date(today.year, today.month + 1, 1) - datetime.timedelta(days=1)
    return start, end


def _period_label(period_type: str, start: datetime.date, end: datetime.date) -> str:
    if period_type == ReviewTarget.PeriodType.WEEK:
        if start.month == end.month:
            return f"Week of {start.strftime('%b')} {start.day}–{end.day}"
        return f"Week of {start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}"
    return start.strftime("%B %Y")


def list_targets_for_shop(*, shop_id: int, org_id: int) -> list[dict[str, object]]:
    targets = list(ReviewTarget.objects.filter(shop_id=shop_id, organisation_id=org_id))
    if not targets:
        return []

    today = datetime.date.today()

    # Compute period bounds once per period_type (max 2)
    bounds: dict[str, tuple[datetime.date, datetime.date]] = {
        t.period_type: _current_period_bounds(t.period_type) for t in targets
    }

    # Single review query covering the union of all period ranges
    min_start = min(b[0] for b in bounds.values())
    max_end = max(b[1] for b in bounds.values())

    raw_datetimes = list(
        Review.objects.filter(
            shop_id=shop_id,
            review_create_time__date__gte=min_start,
            review_create_time__date__lte=max_end,
            deleted_at__isnull=True,
        ).values_list("review_create_time", flat=True)
    )

    # Bucket each review date into the right period_type
    counts: dict[str, int] = {pt: 0 for pt in bounds}
    for dt in raw_datetimes:
        d = dt.date() if hasattr(dt, "date") else dt
        for pt, (start, end) in bounds.items():
            if start <= d <= end:
                counts[pt] += 1

    results = []
    for t in targets:
        start, end = bounds[t.period_type]
        received = counts[t.period_type]
        pct = min(100, floor(received / t.target_count * 100)) if t.target_count > 0 else 0
        results.append(
            {
                "id": t.pk,
                "period_type": t.period_type,
                "target_count": t.target_count,
                "received_count": received,
                "pct": pct,
                "period_label": _period_label(t.period_type, start, end),
                "days_remaining": max(0, (end - today).days),
            }
        )

    return results
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
pytest apps/shops/tests/test_target_selectors.py -v
```

Expected: 10 tests pass

- [ ] **Step 5: Commit**

```bash
git add apps/shops/selectors/targets.py apps/shops/tests/test_target_selectors.py
git commit -m "feat(shops): rewrite selector for recurring targets with current-period progress"
```

---

## Task 6: Update serializers

**Files:**
- Modify: `apps/shops/serializers.py`

- [ ] **Step 1: Replace the three ReviewTarget serializers**

In `apps/shops/serializers.py`, replace the three `ReviewTarget*` serializer classes at the bottom of the file with:

```python
class ReviewTargetReadSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    period_type = serializers.CharField()
    target_count = serializers.IntegerField()
    received_count = serializers.IntegerField()
    pct = serializers.IntegerField()
    period_label = serializers.CharField()
    days_remaining = serializers.IntegerField()


class ReviewTargetWriteSerializer(serializers.Serializer):  # type: ignore[type-arg]
    period_type = serializers.ChoiceField(choices=ReviewTarget.PeriodType.choices)
    target_count = serializers.IntegerField(min_value=1)
```

Remove `ReviewTargetCreateSerializer` and `ReviewTargetUpdateSerializer` entirely (they're replaced by `ReviewTargetWriteSerializer`).

- [ ] **Step 2: Run existing tests to confirm serializers don't break import chain**

```bash
pytest apps/shops/tests/ -v --tb=short 2>&1 | tail -20
```

Expected: selector and service tests still pass; view tests will fail (that's expected — fixed in Task 7).

- [ ] **Step 3: Commit**

```bash
git add apps/shops/serializers.py
git commit -m "feat(shops): update ReviewTarget serializers — read (period_label), write (period_type + target_count)"
```

---

## Task 7: Update views — simplified ViewSet + template view

**Files:**
- Modify: `apps/shops/views.py`

- [ ] **Step 1: Update imports in `apps/shops/views.py`**

Change the import block for target-related items. Find this section near the top:

```python
from apps.shops.serializers import (
    ReviewTargetCreateSerializer,
    ReviewTargetReadSerializer,
    ReviewTargetUpdateSerializer,
    ShopCreateSerializer,
    ShopReadSerializer,
    ShopUpdateSerializer,
)
from apps.shops.services.targets import (
    create_target,
    delete_target,
    update_target,
)
```

Replace with:

```python
from apps.shops.serializers import (
    ReviewTargetReadSerializer,
    ReviewTargetWriteSerializer,
    ShopCreateSerializer,
    ShopReadSerializer,
    ShopUpdateSerializer,
)
from apps.shops.services.targets import (
    delete_target,
    set_target,
)
```

Also add this import near the top with the other Django imports:

```python
from django.shortcuts import get_object_or_404
```

(`render` and `HttpRequest` are already imported.)

- [ ] **Step 2: Replace `ReviewTargetViewSet` with the simplified version**

Find the `ReviewTargetViewSet` class (line ~523) and replace it entirely with:

```python
class ReviewTargetViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    queryset = ReviewTarget.objects.all()
    http_method_names = ["get", "post", "delete", "head", "options"]  # noqa: RUF012

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "destroy"):
            return [RequiresSessionAuth(), IsOrgAdmin(), IsOrgScoped()]
        return [IsOrgScoped()]

    def _get_shop_pk(self) -> int:
        return int(self.kwargs["shop_pk"])

    def _get_org_id(self) -> int:
        user = self.request.user
        if not isinstance(user, User) or user.organisation is None:
            raise drf_serializers.ValidationError({"detail": ["Organisation not found."]})
        return int(user.organisation_id)  # type: ignore[arg-type]

    def _verify_shop_org(self, shop_pk: int, org_id: int) -> None:
        from rest_framework.exceptions import PermissionDenied

        if not Shop.objects.filter(pk=shop_pk, organisation_id=org_id).exists():
            raise PermissionDenied()

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        org_id = self._get_org_id()
        shop_pk = self._get_shop_pk()
        self._verify_shop_org(shop_pk, org_id)
        results = list_targets_for_shop(shop_id=shop_pk, org_id=org_id)
        return Response(ReviewTargetReadSerializer(results, many=True).data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ReviewTargetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not isinstance(user, User):
            raise drf_serializers.ValidationError({"detail": ["Authentication required."]})
        try:
            set_target(
                shop_id=self._get_shop_pk(),
                org_id=self._get_org_id(),
                period_type=serializer.validated_data["period_type"],
                target_count=serializer.validated_data["target_count"],
                created_by=user,
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Shop not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            raise drf_serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
        results = list_targets_for_shop(
            shop_id=self._get_shop_pk(),
            org_id=self._get_org_id(),
        )
        return Response(ReviewTargetReadSerializer(results, many=True).data, status=status.HTTP_200_OK)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            delete_target(
                target_id=int(kwargs["pk"]),
                org_id=self._get_org_id(),
            )
        except ReviewTarget.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 3: Add `shop_targets_view` template view**

At the end of `apps/shops/views.py`, after the OAuth views, add:

```python
# ---------------------------------------------------------------------------
# Shop Targets — dedicated page view
# ---------------------------------------------------------------------------


from django.contrib.auth.decorators import login_required  # noqa: E402 (placed here for locality)


@login_required
def shop_targets_view(request: Any, shop_id: int) -> Any:
    user = request.user
    if not isinstance(user, User) or user.organisation is None:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    shop = get_object_or_404(Shop, pk=shop_id, organisation=user.organisation)
    return render(
        request,
        "org/shop_targets.html",
        {
            "shop_id": shop.pk,
            "shop_name": shop.name,
            "is_org_admin": user.role == User.Role.ORG_ADMIN,
        },
    )
```

Note: move the `login_required` import to the top of `views.py` with the other Django imports (alongside `from django.shortcuts import render`). The inline import above is just to show where it logically goes; ruff will complain if left at module body level — add it to the top-of-file import block.

The correct top-of-file addition:
```python
from django.contrib.auth.decorators import login_required
```

- [ ] **Step 4: Commit**

```bash
git add apps/shops/views.py
git commit -m "feat(shops): simplify ReviewTargetViewSet (POST=upsert, no PATCH), add shop_targets_view"
```

---

## Task 8: Update URL patterns

**Files:**
- Modify: `apps/shops/urls.py`

- [ ] **Step 1: Add the shop targets template view URL**

Replace the entire contents of `apps/shops/urls.py`:

```python
from __future__ import annotations

from django.urls import path

from apps.shops.views import GoogleOAuthCallbackView, GoogleOAuthStartView, shop_targets_view

urlpatterns = [
    path("oauth/google/start/", GoogleOAuthStartView.as_view(), name="oauth_google_start"),
    path("oauth/google/callback/", GoogleOAuthCallbackView.as_view(), name="oauth_google_callback"),
    path(
        "admin/org/shops/<int:shop_id>/targets/",
        shop_targets_view,
        name="shop_targets",
    ),
]
```

- [ ] **Step 2: Verify URL resolves**

```bash
python manage.py shell -c "from django.urls import reverse; print(reverse('shop_targets', kwargs={'shop_id': 1}))"
```

Expected: `/admin/org/shops/1/targets/`

- [ ] **Step 3: Commit**

```bash
git add apps/shops/urls.py
git commit -m "feat(shops): add /admin/org/shops/<id>/targets/ URL"
```

---

## Task 9: Update view tests

**Files:**
- Modify: `apps/shops/tests/test_target_views.py`

- [ ] **Step 1: Write the new tests**

Replace the entire contents of `apps/shops/tests/test_target_views.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import pytest
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
        org, _admin, client = org_admin_client
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
        assert "period_label" in row

    def test_staff_can_list_own_shop(self, staff_client):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        shop = ShopFactory()
        client = APIClient()
        resp = client.get(f"/api/v1/shops/{shop.pk}/targets/")
        assert resp.status_code in (401, 403)

    def test_cannot_list_other_orgs_shop(self, org_admin_client):
        _org, _admin, client = org_admin_client
        other_shop = ShopFactory()
        resp = client.get(f"/api/v1/shops/{other_shop.pk}/targets/")
        assert resp.status_code in (403, 404)


@pytest.mark.django_db
class TestTargetSet:
    def test_org_admin_creates_target(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "MONTH", "target_count": 200}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 200
        assert ReviewTarget.objects.filter(shop=shop, period_type="MONTH", target_count=200).exists()

    def test_org_admin_upserts_existing_target(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        ReviewTargetFactory(shop=shop, organisation=org, period_type="MONTH", target_count=50)
        payload = {"period_type": "MONTH", "target_count": 999}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 200
        # Only one MONTH target should exist
        assert ReviewTarget.objects.filter(shop=shop, period_type="MONTH").count() == 1
        assert ReviewTarget.objects.get(shop=shop, period_type="MONTH").target_count == 999

    def test_response_contains_updated_list(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "WEEK", "target_count": 10}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert any(r["period_type"] == "WEEK" for r in resp.data)

    def test_staff_cannot_set(self, staff_client, bypass_session_auth):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "MONTH", "target_count": 50}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 403

    def test_target_count_zero_returns_400(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        payload = {"period_type": "MONTH", "target_count": 0}
        resp = client.post(f"/api/v1/shops/{shop.pk}/targets/", payload, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTargetDelete:
    def test_org_admin_deletes(self, org_admin_client, bypass_session_auth):
        org, _admin, client = org_admin_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 204
        assert not ReviewTarget.objects.filter(pk=t.pk).exists()

    def test_staff_cannot_delete(self, staff_client, bypass_session_auth):
        org, _staff, client = staff_client
        shop = ShopFactory(organisation=org)
        t = ReviewTargetFactory(shop=shop, organisation=org)
        resp = client.delete(f"/api/v1/shops/{shop.pk}/targets/{t.pk}/")
        assert resp.status_code == 403

    def test_wrong_org_returns_404(self, org_admin_client, bypass_session_auth):
        _org, _admin, client = org_admin_client
        other_shop = ShopFactory()
        t = ReviewTargetFactory(shop=other_shop, organisation=other_shop.organisation)
        resp = client.delete(f"/api/v1/shops/{other_shop.pk}/targets/{t.pk}/")
        assert resp.status_code in (403, 404)
```

- [ ] **Step 2: Run all target tests**

```bash
pytest apps/shops/tests/test_target_services.py apps/shops/tests/test_target_selectors.py apps/shops/tests/test_target_views.py -v
```

Expected: all pass

- [ ] **Step 3: Run full shops test suite**

```bash
pytest apps/shops/tests/ -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add apps/shops/tests/test_target_views.py
git commit -m "test(shops): rewrite target view tests for upsert API and new serializer fields"
```

---

## Task 10: Frontend types and API

**Files:**
- Create: `frontend/src/widgets/shop-targets/types.ts`
- Create: `frontend/src/widgets/shop-targets/api.ts`

- [ ] **Step 1: Create types**

```typescript
// frontend/src/widgets/shop-targets/types.ts
export interface TargetRow {
  id: number;
  period_type: "WEEK" | "MONTH";
  target_count: number;
  received_count: number;
  pct: number;
  period_label: string;
  days_remaining: number;
}

export interface SetTargetPayload {
  period_type: "WEEK" | "MONTH";
  target_count: number;
}
```

- [ ] **Step 2: Create API module**

```typescript
// frontend/src/widgets/shop-targets/api.ts
import type { TargetRow, SetTargetPayload } from "./types";

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function reqHeaders(method: string): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (method !== "GET") h["X-CSRFToken"] = getCsrfToken();
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
  const data =
    resp.status === 204 ? (undefined as T) : ((await resp.json().catch(() => null)) as T);
  if (!resp.ok) throw new ApiError(resp.status, data);
  return data;
}

export async function listTargets(shopId: number): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    credentials: "same-origin",
    headers: reqHeaders("GET"),
  });
  return handle<TargetRow[]>(resp);
}

export async function setTarget(
  shopId: number,
  payload: SetTargetPayload,
): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    method: "POST",
    credentials: "same-origin",
    headers: reqHeaders("POST"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow[]>(resp);
}

export async function deleteTarget(shopId: number, targetId: number): Promise<void> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: reqHeaders("DELETE"),
  });
  return handle<void>(resp);
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "shop-targets" | head -20
```

Expected: no errors in the new files

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/shop-targets/
git commit -m "feat(frontend): add shop-targets types and API module"
```

---

## Task 11: ShopTargetsWidget

**Files:**
- Create: `frontend/src/widgets/shop-targets/ShopTargetsWidget.tsx`

- [ ] **Step 1: Create the widget**

```tsx
// frontend/src/widgets/shop-targets/ShopTargetsWidget.tsx
import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteTarget, listTargets, setTarget } from "./api";
import type { TargetRow } from "./types";

interface Props {
  shopId: number;
  shopName: string;
  isOrgAdmin: boolean;
}

function barColor(pct: number): string {
  if (pct >= 70) return "bg-green";
  if (pct >= 40) return "bg-amber";
  return "bg-red";
}

interface CardProps {
  periodType: "WEEK" | "MONTH";
  row: TargetRow | undefined;
  isOrgAdmin: boolean;
  shopId: number;
  onChanged: () => void;
}

function TargetCard({ periodType, row, isOrgAdmin, shopId, onChanged }: CardProps) {
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = periodType === "WEEK" ? "Weekly" : "Monthly";

  function startEdit() {
    setInputValue(row ? String(row.target_count) : "");
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setError(null);
  }

  async function handleSave() {
    const count = parseInt(inputValue, 10);
    if (Number.isNaN(count) || count < 1) {
      setError("Enter a whole number ≥ 1");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setTarget(shopId, { period_type: periodType, target_count: count });
      setEditing(false);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? "Failed to save. Try again." : "Unexpected error.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!row) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteTarget(shopId, row.id);
      setConfirmDelete(false);
      onChanged();
    } catch {
      setError("Failed to delete. Try again.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="bg-white border border-line rounded-lg p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-[13.5px] font-semibold text-ink">{label}</span>
        {row && <span className="text-[12px] text-muted">{row.period_label}</span>}
      </div>

      {row ? (
        <>
          <div>
            <div className="h-2 bg-line-soft rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${barColor(row.pct)}`}
                style={{ width: `${row.pct}%` }}
              />
            </div>
            <div className="flex justify-between mt-1.5">
              <span className="text-[12.5px] text-ink">
                {row.received_count} / {row.target_count} reviews
              </span>
              <span className="text-[12px] text-muted">{row.pct}%</span>
            </div>
          </div>

          <span className="text-[12px] text-muted">
            {row.days_remaining === 0
              ? "Last day of period"
              : `${row.days_remaining} day${row.days_remaining !== 1 ? "s" : ""} remaining`}
          </span>

          {error && <p className="text-[12px] text-red">{error}</p>}

          {isOrgAdmin && (
            <>
              {editing ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    className="w-20 border border-line rounded px-2 py-1 text-[13px] focus:outline-none focus:ring-1 focus:ring-yellow"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={saving}
                    className="px-3 py-1 bg-yellow text-black text-[13px] font-semibold rounded hover:bg-yellow-hover disabled:opacity-50"
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="px-3 py-1 text-[13px] text-ink border border-line rounded hover:bg-line-soft"
                  >
                    Cancel
                  </button>
                </div>
              ) : confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-[12.5px] text-ink">Remove this target?</span>
                  <button
                    type="button"
                    onClick={() => void handleDelete()}
                    disabled={deleting}
                    className="px-3 py-1 text-[13px] text-red border border-red rounded hover:bg-red/10 disabled:opacity-50"
                  >
                    {deleting ? "Deleting…" : "Delete"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="px-3 py-1 text-[13px] text-ink border border-line rounded hover:bg-line-soft"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={startEdit}
                    className="px-3 py-1 text-[13px] text-ink border border-line rounded hover:bg-line-soft"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="px-3 py-1 text-[13px] text-red border border-line rounded hover:bg-line-soft"
                  >
                    Delete
                  </button>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <p className="text-[13px] text-muted">No target set.</p>
          {error && <p className="text-[12px] text-red">{error}</p>}
          {isOrgAdmin &&
            (editing ? (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  className="w-20 border border-line rounded px-2 py-1 text-[13px] focus:outline-none focus:ring-1 focus:ring-yellow"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className="px-3 py-1 bg-yellow text-black text-[13px] font-semibold rounded hover:bg-yellow-hover disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="px-3 py-1 text-[13px] text-ink border border-line rounded hover:bg-line-soft"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={startEdit}
                className="self-start px-3 py-1.5 text-[13px] font-medium text-ink border border-line rounded hover:bg-line-soft"
              >
                + Set Target
              </button>
            ))}
        </>
      )}
    </div>
  );
}

export function ShopTargetsWidget({ shopId, shopName, isOrgAdmin }: Props) {
  const [targets, setTargets] = useState<TargetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setTargets(await listTargets(shopId));
    } catch {
      setLoadError("Could not load targets. Try refreshing.");
    } finally {
      setLoading(false);
    }
  }, [shopId]);

  useEffect(() => {
    void load();
  }, [load]);

  const weekly = targets.find((t) => t.period_type === "WEEK");
  const monthly = targets.find((t) => t.period_type === "MONTH");

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-[13px] text-muted mb-4">
        <a href="/admin/org/shops/" className="hover:text-ink">
          Shops
        </a>
        <span>/</span>
        <span className="text-ink">{shopName}</span>
        <span>/</span>
        <span className="text-ink font-medium">Review Targets</span>
      </nav>

      <h1 className="text-[18px] font-semibold text-ink mb-6">Review Targets</h1>

      {loading ? (
        <p className="text-[13px] text-muted">Loading…</p>
      ) : loadError ? (
        <p className="text-[13px] text-red">{loadError}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TargetCard
            periodType="WEEK"
            row={weekly}
            isOrgAdmin={isOrgAdmin}
            shopId={shopId}
            onChanged={() => void load()}
          />
          <TargetCard
            periodType="MONTH"
            row={monthly}
            isOrgAdmin={isOrgAdmin}
            shopId={shopId}
            onChanged={() => void load()}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "shop-targets" | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/widgets/shop-targets/ShopTargetsWidget.tsx
git commit -m "feat(frontend): add ShopTargetsWidget with weekly/monthly cards"
```

---

## Task 12: Entrypoint, Django template, and Vite registration

**Files:**
- Create: `frontend/src/entrypoints/shop-targets.tsx`
- Create: `templates/org/shop_targets.html`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Create the entrypoint**

```tsx
// frontend/src/entrypoints/shop-targets.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ShopTargetsWidget } from "../widgets/shop-targets/ShopTargetsWidget";

function mount() {
  const root = document.getElementById("shop-targets-root");
  if (!root || root.dataset.mounted) return;
  root.dataset.mounted = "1";
  const shopId = Number(root.dataset.shopId ?? "0");
  const shopName = root.dataset.shopName ?? "";
  const isOrgAdmin = root.dataset.isOrgAdmin === "true";
  createRoot(root).render(
    <StrictMode>
      <ShopTargetsWidget shopId={shopId} shopName={shopName} isOrgAdmin={isOrgAdmin} />
    </StrictMode>,
  );
}

mount();
document.addEventListener("turbo:load", mount);
```

- [ ] **Step 2: Create the Django template**

```html
{% extends "base_org.html" %}
{% load static django_vite %}

{% block content %}
  <div
    id="shop-targets-root"
    data-shop-id="{{ shop_id }}"
    data-shop-name="{{ shop_name|escapejs }}"
    data-is-org-admin="{{ is_org_admin|yesno:'true,false' }}"
  ></div>
{% endblock %}

{% block extra_js %}
  {% vite_asset 'src/entrypoints/shop-targets.tsx' %}
{% endblock %}
```

Save to: `templates/org/shop_targets.html`

- [ ] **Step 3: Register in vite.config.ts**

In `frontend/vite.config.ts`, find the `input` block and add the new entrypoint:

```typescript
"shop-targets": resolve(__dirname, "src/entrypoints/shop-targets.tsx"),
```

Add it alongside the other entries, e.g. after `"shop-management"`.

- [ ] **Step 4: Build check**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: builds successfully, `shop-targets` appears in the output chunk list

- [ ] **Step 5: Commit**

```bash
git add frontend/src/entrypoints/shop-targets.tsx templates/org/shop_targets.html frontend/vite.config.ts
git commit -m "feat(frontend): add shop-targets entrypoint, Django template shell, Vite registration"
```

---

## Task 13: Update ShopTable — targets action → full navigation

**Files:**
- Modify: `frontend/src/widgets/shop-management/ShopTable.tsx`

- [ ] **Step 1: Find the targets action in SHOP_ACTIONS**

In `ShopTable.tsx`, find this action (around line 28–33):

```typescript
  {
    key: "targets",
    label: "Review Targets",
    icon: <BarChart2 size={14} />,
    onSelect: (r) => dispatchShopEvent("shop:open-targets", r),
  },
```

Replace `onSelect` to navigate with `window.location.href`:

```typescript
  {
    key: "targets",
    label: "Review Targets",
    icon: <BarChart2 size={14} />,
    onSelect: (r) => {
      window.location.href = `/admin/org/shops/${r.id}/targets/`;
    },
  },
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "ShopTable" | head -10
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/widgets/shop-management/ShopTable.tsx
git commit -m "feat(frontend): shop targets action navigates to dedicated page"
```

---

## Task 14: Clean up ShopModals and ShopDetailsModal

**Files:**
- Modify: `frontend/src/widgets/shop-management/ShopModals.tsx`
- Modify: `frontend/src/widgets/shop-management/ShopDetailsModal.tsx`

**ShopModals.tsx changes:**

- [ ] **Step 1: Remove `detailsInitialTab` state and `shop:open-targets` listener**

In `ShopModals.tsx`:

1. Remove the state variable `const [detailsInitialTab, setDetailsInitialTab] = useState<"details" | "targets">("details");`

2. Remove the `shop:open-targets` entry from the event map (the block that sets `setDetailsInitialTab("targets")`):
   ```typescript
   // Remove this entire entry from the map array:
   [
     "shop:open-targets",
     (e) => {
       setSelected((e as CustomEvent<ShopRow>).detail);
       setDetailsInitialTab("targets");
       setDetailsOpen(true);
     },
   ],
   ```
   And simplify the `shop:open-details` handler — remove `setDetailsInitialTab("details")`:
   ```typescript
   [
     "shop:open-details",
     (e) => {
       setSelected((e as CustomEvent<ShopRow>).detail);
       setDetailsOpen(true);
     },
   ],
   ```

3. In the `<ShopDetailsModal>` JSX, remove the `initialTab={detailsInitialTab}` prop and the `onClose` reset of `setDetailsInitialTab("details")`:
   ```tsx
   <ShopDetailsModal
     open={detailsOpen}
     shop={selected}
     isOrgAdmin={isOrgAdmin}
     onClose={() => {
       setDetailsOpen(false);
       setSelected(null);
     }}
     onEdit={() => { ... }}
     ...
   />
   ```

**ShopDetailsModal.tsx changes:**

- [ ] **Step 2: Remove Targets tab, SetTargetModal, useTargets**

In `ShopDetailsModal.tsx`:

1. Remove imports:
   ```typescript
   import { SetTargetModal } from "./SetTargetModal";
   import { TargetsTab } from "./TargetsTab";
   import { useTargets } from "./useTargets";
   ```

2. Remove the `initialTab` prop from the `Props` interface and function signature.

3. Remove these state variables:
   ```typescript
   const [activeTab, setActiveTab] = useState<TabId>(initialTab);
   const [showSetTarget, setShowSetTarget] = useState(false);
   ```
   And the effect `useEffect(() => { if (open) setActiveTab(initialTab); }, [open, initialTab]);`

4. Remove `const targets = useTargets(shop?.id ?? null);`

5. Remove `type TabId = "details" | "targets";` and the `tabs` array.

6. Remove the tab switcher `<div>` (the button row with `{tabs.map(...)}`).

7. In the modal body, replace the conditional rendering:
   ```tsx
   {shop ? (
     activeTab === "details" ? (
       <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
         ...
       </dl>
     ) : (
       <TargetsTab ... />
     )
   ) : (
     <p>No shop selected.</p>
   )}
   ```
   With:
   ```tsx
   {shop ? (
     <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
       {/* all the Row entries unchanged */}
     </dl>
   ) : (
     <p className="text-[13.5px] text-muted">No shop selected.</p>
   )}
   ```

8. Remove the `<SetTargetModal ... />` JSX block at the end of the return.

9. Update `handleModalClose` — remove any reference to `setActiveTab`:
   ```typescript
   const handleModalClose = () => {
     onClose();
   };
   ```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "ShopModals|ShopDetailsModal" | head -20
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/shop-management/ShopModals.tsx frontend/src/widgets/shop-management/ShopDetailsModal.tsx
git commit -m "feat(frontend): remove Targets tab from ShopDetailsModal, remove shop:open-targets from ShopModals"
```

---

## Task 15: Delete old files

**Files:**
- Delete: `frontend/src/widgets/shop-management/SetTargetModal.tsx`
- Delete: `frontend/src/widgets/shop-management/TargetsTab.tsx`
- Delete: `frontend/src/widgets/shop-management/targetsApi.ts`
- Delete: `frontend/src/widgets/shop-management/useTargets.ts`
- Delete: `frontend/src/widgets/action-items/ShopTargetsModal.tsx`

- [ ] **Step 1: Delete the files**

```bash
rm frontend/src/widgets/shop-management/SetTargetModal.tsx
rm frontend/src/widgets/shop-management/TargetsTab.tsx
rm frontend/src/widgets/shop-management/targetsApi.ts
rm frontend/src/widgets/shop-management/useTargets.ts
rm frontend/src/widgets/action-items/ShopTargetsModal.tsx
```

- [ ] **Step 2: Check for remaining imports of the deleted files**

```bash
grep -r "SetTargetModal\|TargetsTab\|targetsApi\|useTargets\|ShopTargetsModal" frontend/src/ --include="*.tsx" --include="*.ts"
```

Expected: no output (no remaining imports)

- [ ] **Step 3: TypeScript build check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 4: Run full Python test suite**

```bash
pytest apps/shops/tests/ -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat(frontend): delete old targets modal/tab files replaced by shop-targets page"
```

---

## Task 16: Final integration check

- [ ] **Step 1: Run all backend tests**

```bash
pytest apps/ -v --tb=short 2>&1 | tail -30
```

Expected: all pass

- [ ] **Step 2: Check no missing migrations**

```bash
python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`

- [ ] **Step 3: Check for dead imports in any modified Python file**

```bash
cd /path/to/repo && python -m ruff check apps/shops/ --select F401 2>&1 | head -20
```

Expected: no unused import errors in shops app

- [ ] **Step 4: Frontend build**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|warning|built in" | head -20
```

Expected: `built in Xs`, no errors

- [ ] **Step 5: Commit (if any lint fixes were needed)**

```bash
git add -A
git commit -m "chore: fix any lint issues after recurring review targets refactor"
```
