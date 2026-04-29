---
status: awaiting_human_verify
trigger: "After user completes Google OAuth consent (clicks Allow), the popup closes immediately and the main window shows 'Connection cancelled. Please try again.' The listing picker never appears."
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T01:30:00Z
---

## Current Focus

hypothesis: ROOT CAUSE CONFIRMED. Django's SecurityMiddleware sets COOP "same-origin" on ALL pages by default. The main window (shop list) has COOP "same-origin" — when the popup navigates to Google (cross-origin) and back, the popup is placed in a different browsing context group and window.opener becomes null. The callback template guard "window.opener && window.opener.postMessage(...)" silently skips the message. postMessage never reaches the main window. The closeWatch then fires onError("closed") when popup closes. Additionally: (2) pollRef is used as success guard but is nulled by 30s timeout path — wrong sentinel, (3) polling auto-selects listings[0] skipping multi-listing picker.
test: Confirmed via Django docs — SECURE_CROSS_ORIGIN_OPENER_POLICY defaults to "same-origin" in Django 3.1+/6.0. Confirmed SecurityMiddleware in MIDDLEWARE list with no override.
expecting: Fix applied in settings + OAuthConnectionSection.tsx
next_action: (1) Add SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups" to base.py. (2) Replace pollRef guard with dedicated successFiredRef boolean in OAuthConnectionSection. (3) Fix polling to not auto-select when listings.length > 1.

## Symptoms

expected: After clicking Allow on Google consent screen, popup should show listing picker OR auto-select single listing and postMessage success to main window then close.
actual: Popup closes after Allow, main window shows "Connection cancelled. Please try again." — listing picker never renders.
errors: "Connection cancelled. Please try again." shown in OAuthConnectionSection. Screenshot shows consent screen still up while main window already shows error.
reproduction: Open Create Shop modal → Connect with Google → Connect Google Business Profile button → complete consent → Allow → popup closes → main window shows error.
started: Never worked — new feature (Phase 8).

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-04-29T00:00:00Z
  checked: Prior investigation notes
  found: OAuth callback URL returns HTTP 200 with 778 bytes (auto-select path for single listing). Callback template sends postMessage({type:"oauth_success"}) then setTimeout(window.close, 50). closeWatch polls every 500ms and was firing onError("closed") before postMessage handler could run.
  implication: Race condition confirmed in prior session. Partial fix applied (600ms delay in closeWatch after detecting popup closed). But issue persists — either delay insufficient, or second problem exists (template not rendering, polling interfering, messageHandler not processing correctly).

- timestamp: 2026-04-29T01:00:00Z
  checked: config/settings/base.py MIDDLEWARE list, Django SecurityMiddleware defaults
  found: SecurityMiddleware is in MIDDLEWARE. Django 3.1+ sets SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin" by default. No override in any settings file. The main window (shop list rendered by shop_list view) gets COOP: same-origin from SecurityMiddleware.
  implication: When popup navigates to Google (cross-origin) and back to our callback, COOP "same-origin" on the opener (main window) causes the browser to sever window.opener. In callback.html, "window.opener && window.opener.postMessage(...)" — window.opener is null, guard silently skips postMessage. Message never delivered. closeWatch fires onError("closed") when popup closes.

- timestamp: 2026-04-29T01:01:00Z
  checked: OAuthConnectionSection.tsx closeWatch logic (lines 83-88)
  found: closeWatch uses "pollRef.current !== null" as "success not yet fired" guard. But cleanup() (called on both success AND 30s timeout) clears pollRef.current = null. After the 30s timeout path fires cleanup(), a subsequent popup close will see pollRef.current === null and NOT call onError — leaving user stuck with no error feedback.
  implication: Wrong sentinel variable. Need a dedicated boolean ref (successFiredRef) that only becomes true on success, not on timeout.

- timestamp: 2026-04-29T01:02:00Z
  checked: OAuthConnectionSection.tsx polling fallback (lines 103-116)
  found: Polling calls onConnected with listings[0] regardless of how many listings exist. If a user has multiple GBP locations, the polling path bypasses the multi-listing picker and silently auto-selects index 0.
  implication: Multi-listing picker is completely bypassed by polling path. Must only auto-select when listings.length === 1, matching the callback template's behavior.

## Resolution

root_cause: Django's SecurityMiddleware sets Cross-Origin-Opener-Policy: same-origin on all responses by default (SECURE_CROSS_ORIGIN_OPENER_POLICY default). When the popup navigates from our domain to Google's consent screen (cross-origin), the browser places it in a new browsing context group and severs window.opener. On return to our callback page, window.opener is null. The callback template's guard "window.opener && window.opener.postMessage(...)" silently skips the postMessage — no success signal is ever sent. closeWatch then fires onError("closed") when the popup closes itself. Two secondary bugs existed: (a) the 30s polling timeout called cleanup() which nulled pollRef, making the closeWatch sentinel incorrect for the post-timeout window; (b) the polling fallback auto-selected listings[0] regardless of count, bypassing the multi-listing picker.

fix: |
  1. config/settings/base.py: Added SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups". This overrides Django's default and lets the popup retain window.opener across the Google redirect, so postMessage works.
  2. OAuthConnectionSection.tsx: Added successFiredRef boolean ref. Reset to false at the start of each handleConnect() call. Set to true on both success and error postMessage handling. closeWatch's 600ms grace period now checks !successFiredRef.current instead of pollRef.current !== null — this correctly survives the 30s polling timeout path.
  3. OAuthConnectionSection.tsx: Polling fallback now only auto-selects when listings.length === 1, matching the callback template's behaviour. Multiple listings are handled by the in-popup picker (user form POST → single-listing template → postMessage).
  4. OAuthConnectionSection.tsx: 30s polling timeout now only clears the polling interval (not all cleanup), preserving closeWatch so onError("closed") still fires if user closes popup after timeout.

verification: Pending human verification.
files_changed:
  - config/settings/base.py
  - frontend/src/widgets/shop-management/OAuthConnectionSection.tsx
