---
status: testing
phase: 33-credit-visibility-staff-scoping
source: [33-VERIFICATION.md]
started: 2026-11-12T02:04:00Z
updated: 2026-11-12T02:04:00Z
---

## Current Test

number: 1
name: Credit colour bands in a real browser
expected: |
  On Shop Details, the Shops list and the composer, shops at roughly 80%, 20%, 3%, 0 and "not enabled" show green, amber, red, dark grey and muted grey respectively, each also readable as text, with acceptable contrast.
awaiting: user response

## Tests

### 1. Credit colour bands in a real browser
expected: Shops at ~80%, 20%, 3%, 0 and "not enabled" render green, amber, red, dark grey and muted grey on Shop Details, the Shops list and the composer; each band is also conveyed as text; contrast is acceptable.
result: [pending]

### 2. Contact Admin mailto
expected: Clicking Contact Admin from the credits card, the Shops-list badge path and the composer opens a mail-client draft to REVIEWBEE_SUPPORT_EMAIL with the encoded subject and a shop/month/balance body, and no review text.
result: [pending]

### 3. Composer at 360px
expected: On a 360px viewport, in every credit state, the composer status line, button label, tone pills and Buy More link do not overflow or clip.
result: [pending]

### 4. Two-Escape modal ordering
expected: With Shop Details open and Buy More opened from the card, the first Escape closes Buy More only and the second closes Shop Details; focus is trapped and restored correctly each time.
result: [pending]

### 5. Screen-reader announcements
expected: Walking the composer through loading, ready, not-enabled, insufficient and a 402, each state change is announced once via the status line, and focus lands on the textarea after a 402.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
