---
phase: 25-org-admin-tag-management-dashboard-polarity
verified: 2026-06-16T12:20:00Z
status: human_needed
score: 5/5 roadmap success criteria verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "templates/org-admin/tags.html now loads django_vite and emits {% block extra_js %}{% vite_asset 'src/entrypoints/tag-management.tsx' %}{% endblock %} — fixed in commit 8389dd4; the React bundle is now delivered to the browser, unblocking SC-1 through SC-4"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Open /admin/org/tags/ as an ORG_ADMIN with canonical tags in the database"
    expected: "The sortable/paginated data table renders with Label, Polarity badge, Review Count, First Seen, and Actions menu; no blank page"
    why_human: "Visual widget mount and table render cannot be verified programmatically"
  - test: "Click Rename on a tag, type a new label, save"
    expected: "Tag label updates in-place (no page reload); attempting to use a duplicate name shows the inline error"
    why_human: "Interactive inline rename UX flow cannot be automated without a browser"
  - test: "Initiate a merge — select source, open modal, pick target, confirm"
    expected: "Modal shows re-maps N reviews, cannot be undone at both steps; after confirm the progress banner appears and polls until the Celery task completes"
    why_human: "Two-step modal UX and Celery async completion cannot be verified without a running browser + worker"
  - test: "Reload the browser mid-merge"
    expected: "Progress banner re-appears from the durable TagMergeJob record (reload survival)"
    why_human: "Reload-survival requires a live browser session with an active merge job"
  - test: "Open the dashboard with mixed canonical tags that have both positive and negative ReviewTags"
    expected: "Mixed tags render as a stacked positive/negative bar; always_positive/always_negative tags render a single-color bar"
    why_human: "Visual chart rendering cannot be verified without a browser and seeded data"
  - test: "Log in as a Staff Admin"
    expected: "Tags nav item is absent from the sidebar; direct navigation to /admin/org/tags/ redirects to login"
    why_human: "Belt-and-braces sidebar absence is a visual check; the view-level redirect is tested automatically but the combined browser flow needs human confirmation"
---

# Phase 25: Org Admin Tag Management & Dashboard Polarity Verification Report

**Phase Goal:** Org Admins and Managers can directly curate their org's canonical vocabulary — viewing, renaming, and merging tags with safe, observable, reversible-where-possible operations — and the dashboard presents tag data with polarity-aware splits, so the self-organising vocabulary stays clean and the analytics reflect it.
**Verified:** 2026-06-16T12:20:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (commit 8389dd4)

---

## Gap Closure Confirmation

The sole blocker from the initial verification has been fixed.

**Gap:** `templates/org-admin/tags.html` rendered `#tag-management-root` but omitted the `{% block extra_js %}{% vite_asset 'src/entrypoints/tag-management.tsx' %}{% endblock %}` block, so the React widget never mounted in the browser.

**Fix (commit 8389dd4 — "fix(25-02): load tag-management React bundle on Tags page"):**

```html
{% extends "base_org.html" %}
{% load static django_vite %}

{% block content %}
  <div id="tag-management-root"></div>
{% endblock %}

{% block extra_js %}
  {% vite_asset 'src/entrypoints/tag-management.tsx' %}
{% endblock %}
```

**Verified against codebase:**

| Check | Result |
|-------|--------|
| `templates/org-admin/tags.html` line 2: `{% load static django_vite %}` | CONFIRMED |
| `templates/org-admin/tags.html` lines 8-10: `{% block extra_js %}{% vite_asset 'src/entrypoints/tag-management.tsx' %}{% endblock %}` | CONFIRMED |
| `templates/base_org.html` line 12: `{% block extra_js %}{% endblock %}` (block exists for override) | CONFIRMED |
| `frontend/vite.config.ts` line 36: `"tag-management"` entry registered | CONFIRMED (from prior report, unchanged) |
| Commit `8389dd4` modifies exactly `templates/org-admin/tags.html`, +5/-1 lines | CONFIRMED |

The fix mirrors the pattern used by every other widget page (`audit-log.html`, `org_dashboard.html`, `shop_list.html`, `team_list.html`). With the bundle now delivered, SC-1 through SC-4 are no longer browser-blocked.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|------------------|--------|----------|
| 1 | Tags page at /admin/org/tags/ showing Label, Polarity badge, Review Count, First Seen — sortable, paginated, query-count-bounded; Staff cannot reach it | VERIFIED | URL resolves; ORG_ADMIN gets 200; Staff redirected (both tested). API sortable/paginated/≤3 queries (tested). Bundle now delivered via {% vite_asset %} in fixed tags.html — widget mounts on #tag-management-root |
| 2 | Inline rename (1–100 chars, unique within org); updates OrgCanonicalTag.label (O(1) FK-only) | VERIFIED | rename_canonical_tag tested: FK-only (ReviewTag rows untouched), label__iexact duplicate guard, title-case, 1-100 chars. 7 service tests pass. API exposed as PATCH /canonical-tags/{id}/rename/ |
| 3 | Merge via modal + searchable target picker + "re-maps N reviews, cannot be undone"; batched merge_canonical_tags task on tag-merge queue under per-org lock; re-points reviews, deletes source, combines review_count, posts completion notification | VERIFIED | Service: single bulk UPDATE ReviewTag FKs → source.delete() → _refresh_review_counts(aggregate) → dispatch_notification(org_admins_only=True), all under distributed_lock + transaction.atomic. Celery route confirmed. Modal shows N reviews count + "cannot be undone" at both steps. test_merge_dispatches_notification passes |
| 4 | Merge progress via HTTP polling — in-progress bar with dismiss, survives reload, completion toast, failure rolls back partial updates (no new WebSocket consumer) | VERIFIED | TagMergeJob model PENDING/IN_PROGRESS/SUCCESS/FAILED, dismissed field, durable DB record. active/ and dismiss/ endpoints tested. useMergeProgress.ts polls at 2_000ms via setInterval, stops on terminal status. MergeProgressBanner has role="progressbar", emitToast on SUCCESS, role="alert" on FAILED. Zero WebSocket usage confirmed. Bundle now loadable |
| 5 | Dashboard tag charts: single count for always_positive/always_negative; positive/negative split for mixed; canonical aggregation includes only reviews where canonical_tag is set | VERIFIED | dashboard_tag_polarity: single grouped query with canonical_tag__organisation_id filter (implies IS NOT NULL per TDASH-02), positive_count/negative_count/total_count annotated. TagPolarityChart uses stackId="a" for both Bar components. 23 dashboard tests pass including test_tag_polarity_excludes_null_canonical |

**Score:** 5/5 roadmap criteria verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/reviews/models.py` | TagMergeJob model | VERIFIED | class TagMergeJob at line 179; Status TextChoices PENDING/IN_PROGRESS/SUCCESS/FAILED; dismissed, processed, total, error_message, denormalized source_label/target_label; composite indexes |
| `apps/reviews/migrations/0014_tagmergejob.py` | TagMergeJob migration | VERIFIED | File exists, contains tagmergejob_org_status_idx |
| `apps/notifications/models.py` | TAG_MERGE_COMPLETE notification type | VERIFIED | TAG_MERGE_COMPLETE = "tag_merge_complete" at line 27 |
| `apps/notifications/migrations/0002_notification_type_tag_merge_complete.py` | Notification migration | VERIFIED | File exists |
| `apps/reviews/services/tag_management.py` | rename_canonical_tag, create_merge_job, merge_canonical_tags | VERIFIED | All three functions implemented; label__iexact guard; _refresh_review_counts import and call; no `review_count +=` |
| `apps/reviews/tasks.py` | merge_canonical_tags_task | VERIFIED | def merge_canonical_tags_task at line 313; bind=True, max_retries=3, retry_backoff=60 |
| `apps/reviews/selectors/canonical_tags.py` | list_canonical_tags_for_org | VERIFIED | def list_canonical_tags_for_org at line 50 |
| `config/settings/base.py` | merge_canonical_tags_task on tag-merge queue | VERIFIED | "apps.reviews.tasks.merge_canonical_tags_task": {"queue": "tag-merge"} at line 130 |
| `apps/reviews/serializers.py` | OrgCanonicalTagReadSerializer, RenameSerializer, TagMergeJobSerializer | VERIFIED | first_seen alias for created_at; all required fields present |
| `apps/reviews/views.py` | OrgCanonicalTagViewSet, TagMergeJobViewSet, tags_page_view | VERIFIED | IsOrgAdmin on both viewsets; @org_admin_required on page view; OrderingFilter on label/review_count/created_at; active/ returns null for no job |
| `templates/org-admin/tags.html` | Tags page mounting #tag-management-root + loading JS bundle | VERIFIED | Mounts #tag-management-root AND loads bundle via {% block extra_js %}{% vite_asset 'src/entrypoints/tag-management.tsx' %}{% endblock %} — fixed in commit 8389dd4 |
| `templates/partials/sidebar_org.html` | Staff-gated Tags nav item | VERIFIED | /admin/org/tags/ inside {% if user.role != "STAFF_ADMIN" %} at line 42 |
| `frontend/src/widgets/tag-management/` (11 files) | Full tag-management React widget | VERIFIED | All 11 files exist; TypeScript compiles; no WebSocket usage |
| `frontend/src/entrypoints/tag-management.tsx` | Vite entrypoint | VERIFIED | Mounts on #tag-management-root with dataset.mounted guard and turbo:load |
| `frontend/vite.config.ts` | tag-management entry registered | VERIFIED | "tag-management" entry at line 36 |
| `apps/dashboard/selectors/aggregations.py` | dashboard_tag_polarity | VERIFIED | Single grouped query, canonical_tag__organisation_id implies IS NOT NULL, positive_count/negative_count/total_count annotated, has_more flag |
| `apps/dashboard/views.py` | DashboardTagPolarityView | VERIFIED | class DashboardTagPolarityView(DashboardApiView) at line 106; endpoint_name="tag-polarity"; inherits IsOrgScoped + cache |
| `apps/dashboard/urls.py` | tag-polarity/ URL | VERIFIED | path("tag-polarity/", ...) at line 20 |
| `frontend/src/widgets/dashboard/TagPolarityChart.tsx` | Stacked recharts polarity chart | VERIFIED | 188 lines; stackId="a" on both Bar components; role="img"; has_more "See all tags" link |
| `frontend/src/widgets/dashboard/DashboardWidget.tsx` | TagPolarityChart wired in | VERIFIED | import + TagPolarityChart at line 265 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| apps/reviews/tasks.py | apps/reviews/services/tag_management.py | merge_canonical_tags(job_id=) | VERIFIED | Thin wrapper confirmed at line 313 |
| apps/reviews/services/tag_management.py | apps/reviews/services/finalise.py | _refresh_review_counts(organisation_id=) | VERIFIED | Import at line 25, call at line 217 |
| config/settings/base.py | tag-merge queue | CELERY_TASK_ROUTES entry | VERIFIED | Line 130 |
| apps/reviews/views.py | apps/reviews/services/tag_management.py | rename/merge actions call services | VERIFIED | rename_canonical_tag + create_merge_job imported and called in viewset actions |
| apps/reviews/views.py | apps/reviews/selectors/canonical_tags.py | list viewset get_queryset | VERIFIED | list_canonical_tags_for_org called in get_queryset() |
| templates/partials/sidebar_org.html | /admin/org/tags/ | Staff-gated nav item | VERIFIED | href="/admin/org/tags/" inside STAFF_ADMIN guard |
| frontend/src/widgets/tag-management/api.ts | /api/v1/reviews/canonical-tags/ + tag-merge-jobs/ | fetch calls | VERIFIED | All 5 endpoints hit correctly |
| frontend/src/widgets/tag-management/useMergeProgress.ts | tag-merge-jobs/active/ | 2s poll, stop on SUCCESS/FAILED | VERIFIED | setInterval(2_000) at line 29 |
| frontend/vite.config.ts | tag-management entrypoint | rollupOptions.input entry | VERIFIED | Line 36 |
| templates/org-admin/tags.html | frontend/src/entrypoints/tag-management.tsx | {% vite_asset %} in extra_js block | VERIFIED | Fixed in commit 8389dd4 — block now present at lines 8-10 |
| apps/dashboard/selectors/aggregations.py | ReviewTag canonical_tag | canonical_tag__organisation_id grouped aggregate | VERIFIED | Line 296 |
| frontend/src/widgets/dashboard/TagPolarityChart.tsx | /api/v1/dashboard/tag-polarity/ | fetchTagPolarity() via api.ts | VERIFIED | api.ts line 105 |
| frontend/src/widgets/dashboard/DashboardWidget.tsx | TagPolarityChart | rendered as a dashboard section | VERIFIED | Line 265 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| TagManagementWidget.tsx | rows (localRows) | fetchTags() → GET /api/v1/reviews/canonical-tags/ → list_canonical_tags_for_org() → OrgCanonicalTag.objects.filter() | Yes — DB query | FLOWING (bundle now delivered via fixed tags.html) |
| MergeProgressBanner.tsx | job (TagMergeJobRow) | fetchActiveJob() → GET /api/v1/reviews/tag-merge-jobs/active/ → TagMergeJob.objects.filter() | Yes — DB query | FLOWING (same) |
| TagPolarityChart.tsx | data (TagPolarityResponse) | fetchTagPolarity() → GET /api/v1/dashboard/tag-polarity/ → dashboard_tag_polarity() → ReviewTag aggregate | Yes — DB query | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 7 rename+merge service tests | uv run pytest apps/reviews/tests/test_services.py -k "rename or merge" | 7 PASSED | PASS |
| 7 view tests (access control, list, merge, poll, dismiss) | uv run pytest apps/reviews/tests/test_views.py -k "canonical_tags or tag_merge_job or merge_409 or tags_page" | 7 PASSED | PASS |
| 3 dashboard tag polarity tests | uv run pytest apps/dashboard/tests/test_aggregations.py -k tag_polarity | 3 PASSED (23 total dashboard tests) | PASS |
| Full reviews test suite | uv run pytest apps/reviews/tests/test_services.py apps/reviews/tests/test_views.py | 48 PASSED | PASS |
| No WebSocket in tag-management widget | grep -rn "WebSocket" frontend/src/widgets/tag-management/ | 0 matches | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|----------|
| TMGT-01 | 25-02 | Tags page accessible to ORG_ADMIN, not Staff | SATISFIED | test_tags_page_org_admin_ok + test_tags_page_staff_redirected PASS; sidebar gated; bundle now loads |
| TMGT-02 | 25-02 | List shows Label, Polarity badge, Review Count, First Seen, sortable, paginated, query-bounded | SATISFIED | OrgCanonicalTagReadSerializer + OrderingFilter + ≤3 queries tested; widget loads |
| TMGT-03 | 25-01 | Rename inline, 1-100 chars, unique, updates OrgCanonicalTag.label | SATISFIED | 7 service tests pass; O(1) FK-only rename confirmed |
| TMGT-04 | 25-03 | Merge modal with searchable target picker + warning | SATISFIED | TagMergeModal.tsx built with two-step UX and N-reviews warning; bundle now loadable |
| TMGT-05 | 25-01 | Merge Celery task on tag-merge queue, per-org lock, FK re-point, delete source, refresh count, notification | SATISFIED | Service + task + Celery route confirmed; test_merge_dispatches_notification PASSES |
| TMGT-06 | 25-01, 25-03 | HTTP polling progress: in-progress bar, dismiss, reload survival, toast, failure rollback | SATISFIED | TagMergeJob durable record + active/dismiss endpoints tested; useMergeProgress polls at 2s; bundle now loadable |
| TDASH-01 | 25-04 | Dashboard shows single count for always_*/stacked split for mixed | SATISFIED | TagPolarityChart with stackId="a"; dashboard loads correctly |
| TDASH-02 | 25-04 | Canonical aggregation includes only reviews with canonical_tag set | SATISFIED | canonical_tag__organisation_id filter implies IS NOT NULL; test_tag_polarity_excludes_null_canonical PASSES |

---

### Anti-Patterns Found

No blockers. No `TBD`, `FIXME`, or `XXX` debt markers found in any phase-modified files. No stub returns in rendering paths. No `review_count +=` naive-sum found in tag_management.py.

---

### Human Verification Required

All automated checks pass. The following items require a live browser (and for merge progress, a running Celery worker) to confirm end-to-end UX behaviour.

#### 1. Tags page renders the widget

**Test:** Open /admin/org/tags/ as an ORG_ADMIN with canonical tags in the database.
**Expected:** Sortable/paginated data table renders with Label, Polarity badge (coloured), Review Count, First Seen, and a three-dot Actions menu. No blank page.
**Why human:** Visual widget mount and table render cannot be verified programmatically.

#### 2. Inline rename UX

**Test:** Click the Actions menu on a tag row, select "Rename", type a new label, press Enter (or click Save Label).
**Expected:** The row updates in-place with the new label; no page reload; attempting a duplicate name shows the inline error.
**Why human:** Interactive rename flow requires a browser.

#### 3. Merge modal two-step UX

**Test:** Click "Merge into…" on a tag, pick a target, click Proceed, confirm.
**Expected:** Step 1 shows searchable target picker with the "All N reviews tagged… cannot be undone" text; Step 2 shows AlertTriangle with "Re-map N reviews" confirm; after confirm the progress banner appears.
**Why human:** Multi-step modal interaction and async task completion require a live browser + Celery worker.

#### 4. Merge progress reload survival

**Test:** Start a merge, then reload the browser tab before the task completes.
**Expected:** Progress banner re-appears from the durable TagMergeJob record.
**Why human:** Requires an active merge job and a browser reload.

#### 5. Dashboard polarity chart visual

**Test:** Open the dashboard with an org that has mixed canonical tags (tags with both positive and negative ReviewTags) and always_positive/always_negative tags.
**Expected:** Mixed tags render as stacked green+red bars; always_* tags render single-colour bars; tooltip shows pos/neg breakdown for mixed and total for single.
**Why human:** Visual chart rendering and stacked bar differentiation require a browser with seeded data.

#### 6. Staff admin access guard (belt-and-braces)

**Test:** Log in as a Staff Admin; inspect the sidebar; attempt to navigate directly to /admin/org/tags/.
**Expected:** Tags nav item is absent from the sidebar; direct URL access redirects to login (not a blank page or 500).
**Why human:** Combined browser + sidebar visual + redirect flow check. (The view-level redirect is tested automatically via test_tags_page_staff_redirected PASSED, but the combined browser flow needs human confirmation.)

---

## Summary

All five roadmap success criteria are now VERIFIED. The sole blocker from the initial verification — the missing `{% vite_asset %}` call in `templates/org-admin/tags.html` — was fixed in commit `8389dd4`. The template now loads `django_vite` and emits the `extra_js` block, matching the audit-log page pattern used by every other widget page in the codebase. All backend services, API endpoints, Celery task routing, DB models, migrations, and frontend widget files were already correct and fully tested before the fix. The dashboard (SC-5) was unaffected throughout. Six human verification items remain for browser/UX confirmation; no automated blockers remain.

---

_Verified (initial): 2026-06-16T14:30:00Z_
_Re-verified (gap closed): 2026-06-16T12:20:00Z_
_Verifier: Claude (gsd-verifier)_
