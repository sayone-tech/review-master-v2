---
status: fixing
trigger: "Production notifications show '1 new review' and '1 review synced' for FRUITBAE Kakkanad, FRUITBAE Thondayad, and FRUITBAE® | Thodupuzha — but the Reports page (last 4 days) shows only FRUITBAE® | Thodupuzha actually received 1 new review."
created: 2026-05-15T00:00:00Z
updated: 2026-05-15T06:30:00Z
---

## Current Focus

hypothesis: CONFIRMED AND FIXED. Old reviews (2019) re-surfaced by Google were new-to-DB, triggering notifications. Fix applied: recency filter in _schedule_new_review_dispatch skips notification for reviews with review_create_time older than 5 days.
test: ruff-check and ruff-format pass. Logic verified: Review.objects.filter(..., review_create_time__gte=recency_cutoff).count() — only recent reviews are counted for the notification title.
expecting: After deploy, syncs that discover old re-surfaced reviews will silently store them but not fire a notification. Genuinely new reviews (within 5 days) will still notify.
next_action: Await human verification in production after deploy

## Symptoms

expected: Notifications should only fire for stores that actually received new reviews. "1 new review at X" means X got a new review. "1 review synced at X" means sync happened and found something new.
actual: Notifications appearing for 3 stores (Kakkanad, Thondayad, Thodupuzha) but reports show only 1 store (Thodupuzha) has new reviews in last 4 days. The notifications appear to be duplicated/ghost fired for stores with no new reviews.
errors: None known — this is a logic bug, not a crash.
reproduction: Check notification bell — shows 8+ notifications across 3 stores spanning "1d ago" and "2d ago". Reports page for same period shows only 1 store with 1 review.
started: Started after May 11 deploy of commit 1bb8c6a ("fix on incremental sync"). Before that, no notifications fired because the dispatch was broken in a different way.

## Eliminated

- hypothesis: Notifications fire on every sync regardless of new reviews
  evidence: CloudWatch logs show new_review_summary_notification_dispatched only fires when fetched>0. Syncs with fetched=0 (vast majority) produce no notification logs.
  timestamp: 2026-05-15

- hypothesis: The notification count (fetched=N) is wrong (total vs new reviews)
  evidence: Commit 1bb8c6a on May 11 fixed exactly this bug. Before: returned len(rows) (total page size). After: returns len(new_google_review_ids) (truly new). Current code is correct.
  timestamp: 2026-05-15

- hypothesis: Ghost notifications for stores with literally zero new reviews
  evidence: Every notification-dispatching sync in CloudWatch shows fetched=1 alongside the notification. The reviews ARE genuinely new-to-DB. The mismatch is in review_create_time.
  timestamp: 2026-05-15

## Evidence

- timestamp: 2026-05-15
  checked: CloudWatch worker logs filter "new_review_summary_notification_dispatched" last 4 days
  found: 8 notifications total: shop_id=7 (3x), shop_id=5 (1x), shop_id=3 (2x), shop_id=6 (1x). Count always=1.
  implication: Notifications fire correctly — only when a genuinely new google_review_id appears in the DB.

- timestamp: 2026-05-15
  checked: Shop ID mapping via SSM shell
  found: shop_id=3=FRUITBAE® Thodupuzha, shop_id=5=FRUITBAE Thondayad, shop_id=6=FRUITBAE Kakkanad, shop_id=7=Vagamon Zipline
  implication: All 4 FRUITBAE shops (+ Vagamon) received at least 1 notification. Not just 3.

- timestamp: 2026-05-15
  checked: sync_shop_reviews_task.success logs at the exact timestamps of notification dispatches
  found: Every notification-firing sync shows fetched=1 soft_deleted=1. Example: shop_id=6 at 11:25 May 13 = fetched=1 soft_deleted=1.
  implication: The pattern fetched=1 soft_deleted=1 means 1 review appeared that wasn't previously in DB, and 1 review disappeared from Google results.

- timestamp: 2026-05-15
  checked: DB query for reviews with created_at >= 2026-05-11 for shops 3, 5, 6
  found:
    - shop_id=3 review created 2026-05-13 14:14 has review_create_time=2026-05-13 13:34 (genuinely new)
    - shop_id=3 review created 2026-05-13 08:04 has review_create_time=2024-04-07 (1+ year old)
    - shop_id=6 review created 2026-05-13 11:25 has review_create_time=2019-12-07 (6+ years old)
    - shop_id=5 review created 2026-05-12 16:18 has review_create_time=2019-06-26 (7+ years old)
  implication: Kakkanad and Thondayad notifications are for reviews written in 2019 that Google only now returned in the API. Reports page filters by review_create_time so they don't appear in "last 4 days".

- timestamp: 2026-05-15
  checked: git diff 1bb8c6a~1..1bb8c6a apps/reviews/services/sync.py
  found: One-line change on May 11 13:22: return len(rows) -> return len(new_google_review_ids). This is what fixed the broken incremental sync counting. The "fix on incremental sync" commit that enabled correct notifications.
  implication: Before this fix, ALL reviews were counted as new on every sync but notifications didn't fire (dispatch was wired differently). After this fix, only genuinely new-to-DB reviews trigger notifications — which is correct but exposes the old-review issue.

- timestamp: 2026-05-15
  checked: AuditLog for shops 5 and 6 initial backfill
  found: Initial backfill on May 8 2026: shop_id=5 fetched 3472, shop_id=6 fetched 3209. These were the complete review sets at that time.
  implication: The 2019 reviews were NOT in the initial backfill. They appeared in the Google API at a later date. Google sometimes re-surfaces old reviews after location merges or review migrations.

## Resolution

root_cause: |
  When Google re-surfaces an old review (one that wasn't in the initial backfill — likely due to
  a Google review migration or location merge), the system correctly identifies it as new-to-DB
  and fires a "1 new review at X" notification. The review's review_create_time is its original
  creation date (e.g., 2019), not the date Google returned it.

  The Reports page filters reviews by review_create_time, so these 2019 reviews don't appear
  in the "last 4 days" filter. This creates a mismatch: the bell shows "1 new review at
  FRUITBAE Kakkanad" but the Reports page shows no new reviews for that store — because the
  review is real, but it was written 7 years ago.

  The notification is technically not wrong — there IS a new review in the database for that
  store. The notification's implicit promise ("this review was posted recently") is what's wrong.

  Affected shops: shop_id=5 (FRUITBAE Thondayad, review_create_time=2019-06-26),
  shop_id=6 (FRUITBAE Kakkanad, review_create_time=2019-12-07).
  Thodupuzha (shop_id=3) had 2 notifications: one for a 2024 review (still old, won't show
  in last-4-days) and one for a genuinely recent review (2026-05-13, which DOES show).

fix: |
  Option A implemented with 5-day threshold (user-approved).

  In _schedule_new_review_dispatch (apps/reviews/services/sync.py):
  - Added module-level constant: _NEW_REVIEW_RECENCY_DAYS = 5
  - Added import: timedelta (from datetime)
  - After receiving new_google_review_ids, query DB for count of those reviews
    whose review_create_time >= now() - 5 days
  - Use that recent_count (not len(new_google_review_ids)) for the notification
  - If recent_count == 0, return early — no notification dispatched
  - Old re-surfaced reviews are still upserted silently; only notification is skipped

  Diff summary:
  + _NEW_REVIEW_RECENCY_DAYS = 5
  + recency_cutoff = dj_timezone.now() - timedelta(days=_NEW_REVIEW_RECENCY_DAYS)
  + recent_count = Review.objects.filter(
  +     shop=shop,
  +     google_review_id__in=new_google_review_ids,
  +     review_create_time__gte=recency_cutoff,
  + ).count()
  + count = recent_count  (replaces: count = len(new_google_review_ids))

  pre-commit: ruff-check PASSED, ruff-format PASSED

verification: Pending human verification in production
files_changed:
  - apps/reviews/services/sync.py
