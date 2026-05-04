"""Phase 13 plan 05 — Notification dispatch service.

dispatch_notification fans out a single event to one Notification row per
eligible recipient in the organisation. Eligibility rules are enforced HERE
(not at call sites) so NOTF-05 cannot be bypassed by a future caller.

Invariants:
  - Recipient must be ORG_ADMIN or STAFF_ADMIN, active, and in the same org.
  - NOTF-05: Brand-scoped action_item notifications NEVER reach Staff users.
  - recipient_ids / exclude_recipient_ids are post-filters on top of the above.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.notifications.models import Notification

if TYPE_CHECKING:
    from apps.action_items.models import ActionItem
    from apps.reviews.models import Review
    from apps.shops.models import Shop


def dispatch_notification(
    *,
    organisation_id: int,
    notification_type: str,
    title: str,
    target_url: str,
    shop: Shop | None = None,
    action_item: ActionItem | None = None,
    review: Review | None = None,
    recipient_ids: list[int] | None = None,
    exclude_recipient_ids: list[int] | None = None,
) -> int:
    """Create Notification rows for all eligible recipients in the org.

    Eligibility:
      - User must belong to ``organisation_id``
      - User role must be ORG_ADMIN or STAFF_ADMIN
      - User must be active
      - If ``action_item`` is provided AND its scope is BRAND, Staff are
        EXCLUDED (NOTF-05). Enforced at the dispatch layer so a future
        miswritten call site cannot leak brand-scope notifications to Staff.
      - ``recipient_ids`` (if provided) restricts to those users.
      - ``exclude_recipient_ids`` (if provided) removes those users.

    Returns the count of Notification rows created.
    """
    # Local import to avoid app-loading cycles (notifications -> accounts).
    from apps.accounts.models import User

    qs = User.objects.filter(
        organisation_id=organisation_id,
        role__in=[User.Role.ORG_ADMIN, User.Role.STAFF_ADMIN],
        is_active=True,
    )
    if recipient_ids is not None:
        qs = qs.filter(pk__in=recipient_ids)
    if exclude_recipient_ids:
        qs = qs.exclude(pk__in=exclude_recipient_ids)

    # NOTF-05: Brand-scoped action items must NEVER reach Staff users.
    if action_item is not None and getattr(action_item, "scope", None) == "BRAND":
        qs = qs.exclude(role=User.Role.STAFF_ADMIN)

    rows = [
        Notification(
            organisation_id=organisation_id,
            recipient=u,
            notification_type=notification_type,
            title=title,
            target_url=target_url,
            shop=shop,
            action_item=action_item,
            review=review,
        )
        for u in qs
    ]
    if not rows:
        return 0
    Notification.objects.bulk_create(rows)
    return len(rows)
