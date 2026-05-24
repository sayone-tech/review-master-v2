# Phase 20: AI Guardrails — Discussion Log

**Initial discussion:** 2026-05-21 (produced D-01 through D-20)
**Update session:** 2026-05-23 (produced D-21 through D-27)

This log captures the 2026-05-23 update only. The original session predates this log file.

## Areas selected for update

User chose: Length limits, Moderation behavior tuning, Failure UX & messaging.

## Length limits

**Q: Input cap firmness (currently 4000 chars hard-truncate)?**
Options: keep / raise to 8000 / env var / per-org.
**Selected:** env var `OPENAI_REVIEW_TEXT_MAX_CHARS` default 4000.
→ D-21.

**Q: Output cap behavior (currently 300 words, sentence-truncate + apologetic note)?**
Options: keep / lower to 150 / env var / soft cap.
**Selected:** keep 300 words, sentence-truncate + note.
→ D-22 (confirms D-08).

## Moderation behavior tuning

**Q: Treat all flagged categories equally, or category-aware?**
Options: any-flag-blocks / high-severity-only / log-but-don't-block.
**Selected:** Block only on high-severity categories.
→ D-23. Block set: sexual/minors, hate/threatening, violence/graphic, self-harm/intent, self-harm/instructions. Other flags logged at INFO.

**Q: Moderation API failure — fail-open or fail-closed?**
Options: fail-closed / fail-open with 1 retry / fail-open silently.
**Selected:** Fail-open with 1 retry, log at ERROR.
→ D-24.

**Q: Should retry_failed_enrichments_task re-try moderated reviews?**
Options: never / after 7 days / explicit skip in queryset filter.
**Selected:** Never retry moderated reviews.
→ D-25.

## Failure UX & messaging

**Q: Input-flag user copy?**
Options: keep current / explain + suggest manual / explain + support contact.
**Selected:** "AI reply isn't available for this review. Please write your reply manually."
→ D-26.

**Q: Output-flag user copy?**
Options: generic AI failure / suggest retry / same as input copy.
**Selected:** Same as input-moderation copy (shared canonical message).
→ D-26 (continued); D-07 updated to use the shared string.

**Q: Generate-with-AI button state for known-moderated reviews?**
Options: always enabled, fail on click / disable / hide.
**Selected:** Always enabled; fail on click. Re-runs moderation server-side each time.
→ D-27.

## Scope creep redirected

None this session — all questions stayed within "implementation choices for already-scoped guardrails."

## Open / deferred

No new deferrals beyond what the original session captured. Token budget + org AI toggle remain deferred to the pricing phase.
