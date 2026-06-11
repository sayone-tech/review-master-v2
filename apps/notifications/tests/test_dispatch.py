"""Phase 13 plan 05 — Tests for the Notification dispatch service.

Covers:
  - Eligibility (org membership, role, active flag)
  - NOTF-05 brand-scope Staff exclusion (enforced at the dispatch layer)
  - recipient_ids / exclude_recipient_ids filters
  - Integration with action_items.lifecycle (assign + create with assignee)
  - Integration with reviews.services.sync new_review dispatch (R4 / NOTF-02)
  - Integration with reviews.services.enrichment promotion + new_action_item
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.accounts.tests.factories import (
    OrgAdminFactory,
    StaffAdminFactory,
    UserFactory,
)
from apps.action_items.models import ActionItem
from apps.action_items.services.lifecycle import (
    assign_action_item,
    create_action_item,
)
from apps.action_items.tests.factories import ActionItemFactory
from apps.notifications.models import Notification
from apps.notifications.services.dispatch import dispatch_notification
from apps.organisations.tests.factories import OrganisationFactory
from apps.reviews.models import Review
from apps.reviews.services import sync as sync_mod
from apps.reviews.tests.factories import ReviewFactory
from apps.shops.tests.factories import ShopFactory

# ---------------------------------------------------------------------------
# Pure dispatch_notification tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dispatch_creates_rows_for_all_org_users():
    org = OrganisationFactory()
    OrgAdminFactory(organisation=org)
    OrgAdminFactory(organisation=org)
    StaffAdminFactory(organisation=org)
    StaffAdminFactory(organisation=org)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_review",
        title="A new review",
        target_url="/admin/org/reviews/?id=1",
    )
    assert count == 4
    assert Notification.objects.filter(organisation=org).count() == 4


@pytest.mark.django_db
def test_dispatch_excludes_other_orgs():
    org = OrganisationFactory()
    other = OrganisationFactory()
    OrgAdminFactory(organisation=org)
    OrgAdminFactory(organisation=other)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_review",
        title="t",
        target_url="/u",
    )
    assert count == 1


@pytest.mark.django_db
def test_dispatch_brand_action_item_excludes_staff():
    """NOTF-05: Staff must NEVER receive brand-scoped action_item notifications."""
    org = OrganisationFactory()
    OrgAdminFactory(organisation=org)
    StaffAdminFactory(organisation=org)
    brand_item = ActionItemFactory(organisation=org, scope=ActionItem.Scope.BRAND, shop=None)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_action_item",
        title="brand item",
        target_url="/u",
        action_item=brand_item,
    )
    assert count == 1
    recipient_roles = list(
        Notification.objects.filter(action_item=brand_item).values_list(
            "recipient__role", flat=True
        )
    )
    assert recipient_roles == [User.Role.ORG_ADMIN]


@pytest.mark.django_db
def test_dispatch_shop_action_item_includes_staff():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    OrgAdminFactory(organisation=org)
    StaffAdminFactory(organisation=org)
    shop_item = ActionItemFactory(organisation=org, scope=ActionItem.Scope.SHOP, shop=shop)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_action_item",
        title="shop item",
        target_url="/u",
        action_item=shop_item,
    )
    assert count == 2


@pytest.mark.django_db
def test_dispatch_recipient_ids_filter():
    org = OrganisationFactory()
    a = OrgAdminFactory(organisation=org)
    OrgAdminFactory(organisation=org)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_review",
        title="t",
        target_url="/u",
        recipient_ids=[a.pk],
    )
    assert count == 1
    assert Notification.objects.filter(recipient=a).count() == 1


@pytest.mark.django_db
def test_dispatch_exclude_recipient_ids():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    other = OrgAdminFactory(organisation=org)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_review",
        title="t",
        target_url="/u",
        exclude_recipient_ids=[actor.pk],
    )
    assert count == 1
    assert not Notification.objects.filter(recipient=actor).exists()
    assert Notification.objects.filter(recipient=other).exists()


@pytest.mark.django_db
def test_dispatch_returns_zero_if_no_eligible_users():
    org = OrganisationFactory()
    # No org/staff admins in this org — only a Superadmin (ineligible) and an
    # inactive Org Admin (ineligible).
    UserFactory(organisation=org, role=User.Role.SUPERADMIN)
    OrgAdminFactory(organisation=org, is_active=False)
    count = dispatch_notification(
        organisation_id=org.pk,
        notification_type="new_review",
        title="t",
        target_url="/u",
    )
    assert count == 0


# ---------------------------------------------------------------------------
# Integration tests — assignment hooks
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_assign_action_item_dispatches_to_new_assignee():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    assignee = StaffAdminFactory(organisation=org)
    item = ActionItemFactory(organisation=org, scope=ActionItem.Scope.SHOP)
    assign_action_item(action_item=item, assignee_id=assignee.pk, actor=actor)
    notifs = Notification.objects.filter(
        action_item=item,
        recipient=assignee,
        notification_type="action_item_assigned",
    )
    assert notifs.count() == 1


@pytest.mark.django_db(transaction=True)
def test_assign_self_does_not_notify_self():
    org = OrganisationFactory()
    actor = OrgAdminFactory(organisation=org)
    item = ActionItemFactory(organisation=org, scope=ActionItem.Scope.SHOP)
    assign_action_item(action_item=item, assignee_id=actor.pk, actor=actor)
    assert not Notification.objects.filter(
        action_item=item, notification_type="action_item_assigned"
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_create_action_item_with_assignee_dispatches_assignment():
    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    actor = OrgAdminFactory(organisation=org)
    assignee = StaffAdminFactory(organisation=org)
    item = create_action_item(
        organisation_id=org.pk,
        title="Fix the espresso machine",
        scope=ActionItem.Scope.SHOP,
        priority=ActionItem.Priority.HIGH,
        source=ActionItem.Source.MANUAL,
        actor=actor,
        shop_id=shop.pk,
        assignee_id=assignee.pk,
    )
    assert (
        Notification.objects.filter(
            action_item=item, recipient=assignee, notification_type="action_item_assigned"
        ).count()
        == 1
    )


# ---------------------------------------------------------------------------
# Integration test — enrichment promotion + dispatch
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_promote_then_dispatch_via_enrichment_flow():
    """Calling enrich_review with mocked OpenAI returning 1 shop + 1 brand
    action item must produce 2 ActionItem rows and dispatch new_action_item
    notifications subject to NOTF-05 (Staff sees only the shop item).
    """
    from apps.integrations.openai.parser import (
        ActionItem as OAIAction,
    )
    from apps.integrations.openai.parser import (
        EnrichmentResult,
    )
    from apps.reviews.services import enrichment as enrichment_mod

    org = OrganisationFactory()
    shop = ShopFactory(organisation=org)
    OrgAdminFactory(organisation=org)
    StaffAdminFactory(organisation=org)
    review = ReviewFactory(
        organisation=org,
        shop=shop,
        comment="Great service but slow coffee",
        enrichment_status=Review.EnrichmentStatus.PENDING,
    )

    fake_result = EnrichmentResult(
        sentiment="positive",
        tags=[],
        action_items=[
            OAIAction(
                title="Speed up coffee service", scope="shop", priority="high", category="other"
            ),
            OAIAction(title="Refresh brand voice", scope="brand", priority="low", category="other"),
        ],
    )
    # AiPricing is required by enrichment._persist_success.calculate_cost.
    # Migration 0002 seeds gpt-4o-mini, but transaction=True tests truncate
    # the table — re-seed for this test only. Use get_or_create to remain
    # idempotent across pytest-django flush behaviours.
    from datetime import UTC, datetime
    from decimal import Decimal as _Decimal

    from django.conf import settings as dj_settings

    from apps.integrations.openai.models import AiPricing

    AiPricing.objects.get_or_create(
        model=dj_settings.OPENAI_MODEL,
        effective_from=datetime(2024, 7, 18, tzinfo=UTC),
        defaults={
            "input_token_price_per_1m": _Decimal("0.150000"),
            "output_token_price_per_1m": _Decimal("0.600000"),
            "cached_token_price_per_1m": _Decimal("0.075000"),
            "effective_to": None,
        },
    )

    fake_usage = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "cached_tokens": 0,
        "total_tokens": 120,
        "latency_ms": 250,
        "langsmith_trace_id": "",
    }

    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield True

    with (
        patch.object(enrichment_mod, "distributed_lock", _lock),
        patch.object(
            enrichment_mod, "call_openai_enrichment", return_value=(fake_result, fake_usage)
        ),
        patch.object(enrichment_mod, "_emit_enrichment_progress"),
        # No progress snapshot → incremental path → dispatch per review immediately.
        patch("apps.reviews.services.progress.read_progress_snapshot", return_value=None),
        # Phase 23 token-bucket guard — mock so tests don't need a live Redis.
        patch.object(enrichment_mod, "openai_token_bucket_depleted", return_value=False),
        patch.object(enrichment_mod, "increment_openai_token_bucket"),
    ):
        enrichment_mod.enrich_review(review_id=review.pk)

    # 2 ActionItems promoted
    items = ActionItem.objects.filter(source_review=review)
    assert items.count() == 2
    # Incremental path: 1 notification dispatched immediately (org_admins_only=True
    # because the batch contains a brand-scoped item — NOTF-05 enforced).
    notifs = Notification.objects.filter(notification_type="new_action_item")
    assert notifs.count() == 1
    # Staff excluded from notification that contains brand items
    assert not notifs.filter(recipient__role=User.Role.STAFF_ADMIN).exists()
    assert notifs.first().action_item is None


# ---------------------------------------------------------------------------
# Integration test — new_review dispatch via sync (R4 / NOTF-02)
# ---------------------------------------------------------------------------


def _api_review(rid: str, comment: str = "Great!", rating: str = "FIVE") -> dict[str, Any]:
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "reviewId": rid,
        "starRating": rating,
        "comment": comment,
        "createTime": now_iso,
        "updateTime": now_iso,
        "reviewer": {"displayName": "Jane", "isAnonymous": False},
    }


@pytest.mark.django_db(transaction=True)
def test_sync_dispatches_new_review_notification_per_new_row():
    """Two new + one already-existing review must dispatch exactly two new_review
    Notification rows per eligible recipient (NOTF-02)."""
    org = OrganisationFactory()
    shop = ShopFactory(
        organisation=org,
        google_refresh_token="rt",
        google_account_name="accounts/123",
        google_location_name="locations/456",
    )
    org_admin = OrgAdminFactory(organisation=org)
    staff = StaffAdminFactory(organisation=org)

    # Pre-existing review — must NOT trigger a new_review notification.
    existing = ReviewFactory(organisation=org, shop=shop, google_review_id="gid-existing")

    page = {
        "reviews": [
            _api_review(existing.google_review_id),  # update path, not new
            _api_review("gid-new-1"),
            _api_review("gid-new-2"),
        ],
        "totalReviewCount": 3,
        "nextPageToken": "",
    }

    @contextlib.contextmanager
    def _lock(_key: str, timeout: int = 300):
        yield True

    with (
        patch.object(sync_mod, "_refresh_access_token", return_value="tok"),
        patch.object(sync_mod, "distributed_lock", _lock),
        patch.object(sync_mod, "list_reviews", return_value=page),
        patch.object(sync_mod, "write_progress_snapshot"),
        patch.object(sync_mod, "clear_progress_snapshot"),
        patch.object(sync_mod, "increment_google_token_bucket"),
        patch.object(sync_mod, "token_bucket_depleted", return_value=False),
        patch.object(sync_mod, "emit_progress_event"),
        # Phase 23: sync.py dispatches via apply_async (not .delay)
        patch("apps.reviews.tasks.enrich_review_task.apply_async"),
    ):
        # incremental trigger so notification dispatch is NOT suppressed
        sync_mod.fetch_and_persist_reviews(shop_id=shop.pk, trigger="incremental")

    new_review_notifs = Notification.objects.filter(notification_type="new_review")
    # One summary notification dispatched to 2 eligible recipients (OrgAdmin + Staff).
    # The summary covers all new reviews in the batch — no per-review FK.
    assert new_review_notifs.count() == 2
    # The existing review must NOT have produced a notification.
    assert not new_review_notifs.filter(review=existing).exists()
    # Both recipients received the summary.
    recipient_ids = set(new_review_notifs.values_list("recipient_id", flat=True))
    assert recipient_ids == {org_admin.pk, staff.pk}
