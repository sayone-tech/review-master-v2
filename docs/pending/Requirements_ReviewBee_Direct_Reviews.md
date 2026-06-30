**REQUIREMENTS DOCUMENT**

ReviewBee — Multi-Tenant Review Management

**Phase 5 — ReviewBee Direct Reviews**

QR Codes, Public Submission, and Source-aware Review Management

Version 1.0 • May 2026

# 1. Document Overview

This document specifies Phase 5 of the ReviewBee platform — direct review collection via QR codes and a public submission page. It builds on the conventions, data model, AI enrichment pipeline, and design system established in Phases 1 through 4.

All global UI patterns, branding, design tokens, accessibility rules, confirmation popup conventions, services-and-selectors pattern, Celery conventions, and AI cost tracking conventions defined in earlier phases apply unchanged to Phase 5 and are not repeated here.

Phase 5 introduces the platform's first public-facing surface: a customer-facing review submission page reached by scanning a shop's QR code. Reviews submitted this way are stored in the same Review table as Google reviews, processed by the same AI enrichment pipeline, and displayed on the same Reviews page — but tagged with a source field that lets the platform distinguish first-party (ReviewBee) feedback from third-party (Google) reviews.

## 1.1 Phase 5 Scope

- Branding update — "ReviewBee" is the canonical product name; appears throughout admin UI, emails, and public pages, often paired with the organisation name
- Per-shop short code generation and unique public URL
- QR code generation (PNG + PDF) with download from Shop Details and quick action on Shops list
- Public review submission page at /r/{short_code} — mobile-first, co-branded
- Six-layer anti-abuse strategy (honeypot, localStorage marker, soft IP rate limit, Cloudflare Turnstile, OpenAI Moderation, logged-in admin blocking)
- Submission ingestion pipeline — store, moderate, queue for AI enrichment (reuses Phase 3b-i pipeline)
- Source field on Review (GOOGLE | REVIEWBEE) with backfill migration
- Reviews page — Source filter and per-card source badge
- ReviewBee-specific reply flow — email-only, sent via Amazon SES, only when reviewer provided email
- Dashboard updates (Phase 4) — Source filter alongside Region/Store/Date
- Notification updates — source indicator in new_review payload
- Thank-you page with Google review deep-link CTA

## 1.2 Out of Scope for Phase 5

- Public review wall page (anonymous browsing of reviews)
- Photo upload on the public submission form
- Phone number capture
- Multi-language public submission form (English only in Phase 5)
- Vanity domains per organisation (e.g., review.acmecoffee.com)
- Editing or deleting an already-submitted review (by the customer)
- Forwarding ReviewBee reviews to Google (one-click cross-posting)
- Automated abuse detection and pattern flagging (data is logged for manual investigation only)
- SMS confirmation of email replies
- Email-thread replies (each email reply is one-shot; the customer cannot reply back through the platform)

## 1.3 Phase Dependencies

- Phase 2 — Shops, Regions, Team scoping (the QR code is per shop)
- Phase 3a-ii — Review and ReviewReply models (extended with source field)
- Phase 3b-i — AI enrichment pipeline (the same pipeline processes ReviewBee submissions)
- Phase 4 — Dashboard (updated with Source filter)
- Amazon SES (Phase 1) — used for email replies to customers

# 2. Branding and Naming

Phase 5 makes the platform's name canonical: "ReviewBee". The name appears throughout the admin UI, all transactional emails, and the public submission pages.

## 2.1 Naming Conventions

| **Surface** | **Display Format** |
| --- | --- |
| Sidebar logo (admin) | ReviewBee wordmark in yellow on black |
| Login page | ReviewBee wordmark + tagline |
| Browser title (admin) | ReviewBee — {Page Title} |
| Browser title (public submission page) | Leave a review for {Shop Name} — ReviewBee |
| Public submission page header | ReviewBee for {Organisation Name} |
| Email subject lines | Prefix with [ReviewBee] for transactional emails |
| Email footer | Sent via ReviewBee — link to https://reviewbee.in |
| Audit log records | user_agent and request_origin fields preserved for support |

## 2.2 Logo Pairing on the Public Page

On the public submission page only, the ReviewBee wordmark is displayed alongside the organisation's name in the header. This makes it clear to the customer who they are leaving a review for, while preserving ReviewBee's identity as the platform.

- Layout: ReviewBee logo on the left, separator dot or subtle divider, organisation name on the right
- Example header: "ReviewBee · Acme Coffee"
- On mobile, the layout stacks: ReviewBee on top, organisation name below in slightly smaller type

## 2.3 Codebase Updates

- Replace any remaining "BrandName" placeholders in templates and React components with "ReviewBee"
- Update favicons and meta tags with ReviewBee branding
- Update email base template (templates/emails/base.html) with the ReviewBee footer
- Update Open Graph tags on the public submission page so shared QR-scan links preview cleanly on social

# 3. QR Code Generation

## 3.1 Short Code Generation

Each shop has a unique short code that is generated when the shop is created. The short code is the public-facing identifier used in the QR URL and is intentionally short for shareability and durability of printed materials.

### Short Code Format

- 8 characters, lowercase alphanumeric (a-z, 0-9)
- Excludes easily-confused characters: 0 (zero), 1 (one), o, l, i — to keep ~32 characters in the alphabet
- Generated using a cryptographically secure random source
- Collision-checked at generation: if the generated code already exists for any shop in the platform (across organisations), regenerate. Retry up to 5 times before raising.
- Stored on the Shop model as short_code field; unique index across the platform
- Example: r/k3m9p2qx, r/h7j4n8wd

### Short Code Lifecycle

- Generated automatically when a shop is created (signal or service hook in apps/stores/services/shops.py)
- Backfill migration generates codes for all existing shops with a single data migration
- Short codes are immutable after creation — printed materials must remain valid
- If a shop is deactivated, the short code remains assigned but the public submission page returns a 410 Gone response (see §4.7)
- If a shop is permanently deleted, the short code is freed and may be reused on a future shop (extremely unlikely given the address space)

## 3.2 Public URL Format

The public URL embedded in every QR code follows a fixed pattern:

https://app.reviewbee.in/r/{short_code}

Notes on the URL:

- HTTPS only — HTTP requests redirect to HTTPS
- Same Django app as the admin UI; the /r/* namespace is unauthenticated
- No subdomain split — keeps deployment simple, but requires careful CSP and CSRF handling (see §4.5)
- Domain is configured in settings as PUBLIC_BASE_URL so it can be overridden in dev (http://localhost:8000) and staging (https://staging.reviewbee.in)

## 3.3 QR Code Image Generation

**Library:** Python qrcode package (mature, open-source, MIT-licensed)

**Error correction level:** H (high) — 30% redundancy. Survives partial damage on printed materials.

**Module style:** Square modules (no fancy rounded modules in Phase 5; can be revisited)

**Background:** White (printable, scanner-friendly)

**Foreground:** ReviewBee black (#0A0A0A)

**Quiet zone:** 4-module border (qrcode default; required for reliable scanning)

## 3.4 QR Card Layouts (Branded Output)

The downloadable QR is not a bare QR image — it is wrapped in a branded card layout containing the QR code, shop name, scan instruction, and ReviewBee logo. Two layouts are generated.

### Digital PNG (600 × 800 px)

- Vertical card layout
- White background with subtle yellow accent border
- Top: ReviewBee wordmark in black
- Center: QR code, ~440px square, centered horizontally
- Below QR: "Scan to leave a review" in bold
- Below scan text: shop name in slightly smaller bold type
- Below shop name: "Powered by ReviewBee" in small gray text
- Margins: 60px on all sides

### Print-ready PDF (A6 size, 105 × 148 mm)

- Same visual layout as PNG, scaled for A6 printing
- CMYK color space (or RGB with embedded ICC profile if CMYK adds complexity)
- Includes 3mm bleed area for professional printing
- Embeds fonts (don't rely on the printer having Inter installed)

### Optional SVG (nice-to-have, ship if low-cost)

- Vector format for designers who want to compose the QR into custom layouts (table tents, posters, menus)
- Same design as PNG, vector-based
- If SVG is non-trivial to add, defer to a later phase

## 3.5 Generation and Storage

QR card images are generated server-side on demand and cached so subsequent downloads are instant.

### Flow

- User clicks Download (PNG or PDF) on the Shop Details page
- Server checks Google Cloud Storage for a cached version at qr-codes/{shop_id}/{format}.{ext}
- If cached: return a signed URL valid for 5 minutes
- If not cached: render the QR card (qrcode library + Pillow for PNG, qrcode + reportlab for PDF), upload to GCS, return signed URL
- Cached objects are immutable (the QR doesn't change for a given shop) so there is no invalidation logic

### Storage Path Convention

qr-codes/{shop_id}/png/v1.png

qr-codes/{shop_id}/pdf/v1.pdf

The v1 suffix anticipates a future redesign of the QR card; bumping to v2 forces regeneration without invalidating already-printed materials (the QR data itself is unchanged).

## 3.6 Where the QR Lives in the Admin UI

### Inline on Shop Details (Primary Surface)

- New section on the Shop Details modal: "Customer Review QR Code"
- Renders the PNG version inline at ~240×320px
- Below the preview: download buttons for PNG and PDF (with download icon)
- Below buttons: the public URL displayed as plain text with a Copy-to-clipboard icon
- Helper text: "Print this QR code or share the URL with your customers to collect reviews directly."

### Quick Action on Shops List

- New row action menu item: "Get QR Code"
- Click → opens the same Shop Details modal scrolled to the QR Code section

### No Standalone Page

There is no dedicated "QR Codes" page in the admin sidebar. The QR is a property of a shop, accessed from the shop's detail view.

# 4. Public Submission Page

## 4.1 Purpose

The public submission page is the customer-facing surface where a person who scans a shop's QR code (or visits the URL directly) can submit a review. The page is mobile-first because the overwhelmingly common entry point is a phone camera scanning the printed QR.

## 4.2 Route and Access

**Route:** /r/{short_code}

**Access:** Public, unauthenticated

**HTTP method:** GET (display form), POST (submit review)

**Authentication:** None required; CSRF token issued on first GET

## 4.3 URL Lookup and Resolution

- Server looks up Shop by short_code
- If not found → 404 page with friendly message and ReviewBee branding ("This review link doesn't exist or has been removed.")
- If shop status is INACTIVE → 410 Gone with message ("This shop is no longer accepting reviews.")
- If shop's organisation is DISABLED (Phase 1 §5.8) → 410 Gone with same message
- Otherwise → render the submission form

## 4.4 Page Layout (Mobile-First)

### Header

- ReviewBee logo (left) + organisation name (right) on a single line on tablet+
- On mobile: ReviewBee logo on top, organisation name below in smaller type
- Beneath header: shop name as the page title (e.g., "Downtown Store") in large bold type
- Below shop name: subtitle "Tell us about your visit"

### Form (Single Column, Generous Spacing)

| **Field** | **Type** | **Required** | **Validation** | **Placeholder / Helper** |
| --- | --- | --- | --- | --- |
| Rating | 5-star picker (interactive) | Yes | 1–5; large tappable stars | Tap to rate |
| Feedback | Textarea | Yes | Min 10 chars, max 4000 chars (matches Google) | Tell us about your experience… |
| Name | Text input | No | Max 100 chars | Your name (optional) |
| Email | Email input | No | Valid email format if provided | Email address (optional, for replies) |
| Honeypot | Hidden text input | Hidden | Must remain empty (bots fill all visible fields) | (not visible to users) |
| Turnstile | Cloudflare widget | Yes | Validates a token from Cloudflare on submit | (rendered by Turnstile) |

### Below the Form

- Helper text: "Your name is optional — leave blank to submit anonymously."
- Helper text: "Your email is optional. Provide it if you'd like the store to be able to reply."
- Privacy note: "Your IP address is recorded for spam prevention. We don't use it for anything else."

### Submit Button

- Primary button, full-width on mobile, max 320px on tablet+
- Label: "Submit Review"
- Disabled until: Rating is set AND Feedback has at least 10 chars AND Turnstile token is valid
- On submit: button shows a spinner; form fields disabled to prevent double submission

### Footer

- "Powered by ReviewBee" link to https://reviewbee.in
- Privacy Policy and Terms links (placeholders for now; legal copy is a separate effort)

## 4.5 Same-App Hosting Considerations

The public submission page is served by the same Django application as the admin UI. This requires careful configuration to keep the two surfaces secure without breaking either.

### CSRF

- CSRF middleware remains enabled globally
- The /r/{short_code} GET handler issues a CSRF token in a cookie (Django's standard behavior)
- The POST handler validates the CSRF token from the form
- Anonymous CSRF works because Django's CSRF doesn't require an authenticated session — it just requires a cookie + matching form token

### Sessions

- The public page does not create or read user sessions
- If a logged-in user visits the public page, their session cookie is present (same domain) — used only by the logged-in admin block check (see §5.6)
- The submission API does not establish a session for the submitting customer

### CSP

- Content-Security-Policy on the /r/* namespace allows: self-hosted scripts, Cloudflare Turnstile script (https://challenges.cloudflare.com), and inline event handlers needed by Turnstile
- CSP for the admin namespace is unchanged

### CORS

- Not applicable — submission is a same-origin POST (form-encoded or JSON)

## 4.6 Logged-in Admin Banner

If a visitor to the public submission page has an active session for the same Django app (i.e., they are logged in as an Org Admin, Manager, Staff, or Superadmin), the page renders normally but with a prominent banner above the form.

### Banner

- Background: amber/warning
- Icon: warning triangle
- Title: "You're signed in"
- Body: "Customer reviews must be submitted by visitors, not by signed-in admins. Please log out (or use a private browsing window) to leave a review."
- Inline action button: "Log out" → posts to logout endpoint, then refreshes the same /r/{short_code} URL

### Submit Disabled

- The Submit button is disabled with a tooltip on hover: "Sign out to submit a review"
- Server-side enforcement: even if the disabled state is bypassed client-side, the POST handler rejects requests where the user is authenticated, returning 403 with a clear message

## 4.7 States

| **State** | **Trigger** | **Display** |
| --- | --- | --- |
| Form (default) | Valid short_code, shop active, anonymous visitor | Render the submission form per §4.4 |
| Form (logged-in admin) | Valid short_code, but visitor has an admin session | Render form with warning banner; submit disabled |
| 404 Not Found | Short code does not exist | Friendly 404 page with ReviewBee branding |
| 410 Gone | Shop is INACTIVE or organisation is DISABLED | "This shop is no longer accepting reviews." |
| Submitting | Form submitted, awaiting server response | Spinner on button; fields disabled |
| Already submitted today (localStorage) | localStorage marker exists for this shop within 24h | Form replaced with "Thanks for your review yesterday — you can submit another one in {hours} hours." |
| Rate limit reached | Too many submissions from this IP for this shop in the last 24h | Form replaced with "We've received a lot of submissions from your network. Please try again later." |
| Moderation rejected | OpenAI Moderation flagged the content | Toast on the page: "We could not accept this submission. If this is a mistake, please contact the store directly." |
| Network error | Submit failed due to network or 5xx | Inline error banner: "Could not submit. Please try again." with the form still populated |
| Success | Submission accepted and stored | Redirect to thank-you page (see §6) |

# 5. Anti-Abuse Strategy

Public submission forms are abuse magnets without protection. Phase 5 implements six complementary layers that together provide meaningful protection without blocking legitimate customers — including those on shared networks like cafes, malls, and offices.

## 5.1 Layer 1 — Honeypot Field

- A hidden text input named website (or another innocuous-looking name) is added to the form
- CSS hides it from real users (display:none and tabindex=-1 and aria-hidden=true)
- Naive bots fill all visible-and-invisible inputs; the field becomes non-empty
- On submit, server rejects any request where the honeypot field is non-empty — silently (return 200 with a fake success page; the bot never knows it was caught)
- Free, low-overhead, catches dumb bots

## 5.2 Layer 2 — localStorage Submission Marker

- On successful submission, write reviewbee_submitted_{short_code} = {iso_timestamp} to localStorage
- On every page load, check this key. If present and < 24 hours old, replace the form with a friendly state (see §4.7)
- Easy to bypass (incognito mode, clear storage) but stops casual duplicate submissions from the same browser
- Free, no server-side cost

## 5.3 Layer 3 — Soft IP Rate Limit

A deliberately permissive IP rate limit catches bots and bulk submissions while leaving room for legitimate shared-network usage (e.g., a family of customers in a cafe).

### Limit

- 5 successful submissions per shop per IP per rolling 24 hours
- Failed submissions (validation error, moderation rejection, honeypot trip) do NOT count toward the limit
- Tracked in Redis using the existing rate-limiting infrastructure (DB index 1)
- Key format: rate:reviewbee_submission:{shop_id}:{ip_hash} where ip_hash is a salted SHA-256 of the IP (avoids storing raw IPs in Redis)

### On Limit Exceeded

- Form replaced with: "We've received a lot of submissions from your network. Please try again later."
- Status code: 429 Too Many Requests
- No retry-after countdown shown to keep the message non-technical

## 5.4 Layer 4 — Cloudflare Turnstile

Cloudflare Turnstile is a free, low-friction CAPTCHA alternative. It runs an invisible challenge for most users (zero clicks) and surfaces a visible challenge only for suspicious traffic. Setup is free and unlimited regardless of traffic volume.

### Setup

- Create a free Cloudflare account
- Configure a Turnstile widget at dash.cloudflare.com → Turnstile
- Copy the site key (used in the public page HTML)
- Copy the secret key (stored in env, GCP Secret Manager in prod)

### Integration

- Site key → settings.TURNSTILE_SITE_KEY (public, can be in client HTML)
- Secret key → settings.TURNSTILE_SECRET_KEY (private, never exposed)
- Turnstile JS embedded on the public submission page; renders the widget in the form
- On submit, the form includes a cf-turnstile-response token field
- Server validates the token by POSTing it to https://challenges.cloudflare.com/turnstile/v0/siteverify with the secret key
- If validation fails or returns an error, the submission is rejected with a friendly error

### Failure Modes

- If Cloudflare's verification API is unreachable, the platform fails closed (rejects the submission with a friendly retry message). This is intentional — fail open would defeat the protection.
- Token expiry: Turnstile tokens are short-lived (~5 minutes). If a user takes longer than that to fill the form, they'll need to re-validate. Frontend handles this via Turnstile's expired-callback hook.

## 5.5 Layer 5 — OpenAI Moderation Pass

Before persisting a submission, run the feedback text and (if provided) the reviewer name through OpenAI's free Moderation API. This catches spam, hate, threats, and other obvious abuse patterns that the other layers can't detect.

### API Used

- OpenAI Moderation API (model: omni-moderation-latest)
- Free for all OpenAI API users — no per-call billing
- Returns a JSON response with category flags (sexual, hate, harassment, self-harm, violence, etc.) and a single overall flagged boolean

### Behavior

- Run synchronously during submission (adds ~100-300ms latency, acceptable)
- If overall flagged is true: do NOT save the review. Return a friendly error to the user.
- If specific category scores exceed a configurable threshold (default 0.5) but the overall flag is false: save the review with moderation_flagged = true and moderation_reasons = [list of category names]. The store owner sees the review with a small "Flagged for review" badge.
- If clean: save the review normally, queue for AI enrichment

### Failure Modes

- If Moderation API call fails (rate limit, network), the submission still proceeds — log the failure but don't block the customer. This is fail open because we have other layers (Turnstile, honeypot) and the GPT enrichment will likely flag obvious abuse during enrichment anyway.
- Audit log entry on every Moderation call: { event: "moderation.call", shop_id, result, latency_ms, error }

## 5.6 Layer 6 — Logged-in Admin Block

If the visitor has an active session for the platform (Org Admin, Manager, Staff, or Superadmin), the submission is blocked at both UI and server level.

### UI

- Banner displayed above the form (see §4.6)
- Submit button disabled with tooltip

### Server

- POST handler checks request.user.is_authenticated
- If authenticated, returns 403 with body: { "error": "signed_in_user_blocked", "message": "Sign out to submit a review." }
- This protection is server-side authoritative — even if the disabled UI is bypassed, the server rejects the submission

## 5.7 Layered Defense Summary

| **Layer** | **Stops** | **Friction for Real Users** |
| --- | --- | --- |
| Honeypot | Naive bots that fill all form fields | None |
| localStorage marker | Casual duplicate submissions from same browser | Helpful ("thanks for your review yesterday") |
| Soft IP rate limit | Bulk submissions from one network | None for typical users; visible if hit |
| Cloudflare Turnstile | Sophisticated bots, automated abuse | Zero clicks for most users; visible challenge for suspicious |
| OpenAI Moderation | Hate, spam, abuse content | None |
| Logged-in admin block | Self-review by admins | Visible to admins only; clear instructions to log out |

## 5.8 Audit Logging for Investigations

Even though automated abuse detection is out of scope for Phase 5, every submission attempt logs sufficient data for manual investigation if a customer or store later reports suspected abuse.

### Logged Per Submission

- submission_id (UUID, primary key of the new Review record if accepted)
- shop_id
- ip_address (raw, in submission_metadata JSONB on the Review row)
- user_agent
- referer (HTTP Referer header)
- turnstile_action (the action parameter passed to Turnstile)
- submitted_at
- anti_abuse_layers_passed (JSONB, e.g., { honeypot: true, turnstile: true, moderation: true, rate_limit: true })
- moderation_flagged (boolean)
- moderation_reasons (array of category names, if flagged)

### Logged Per Rejected Attempt

- Same fields as above, plus:
- rejection_reason (one of: HONEYPOT_TRIPPED, RATE_LIMIT_EXCEEDED, TURNSTILE_FAILED, MODERATION_REJECTED, ADMIN_BLOCKED, INVALID_FORM)
- Stored in a separate SubmissionRejectionLog table to avoid polluting the Review table with rejected attempts
- Retention: 90 days (rejected attempts have no long-term value)

# 6. Submission Processing

## 6.1 Submission Endpoint

**Method:** POST

**Path:** /r/{short_code} (form submission to the same URL as the form display)

**Content-Type:** application/x-www-form-urlencoded (standard form submission) — JSON also accepted for future API integrations

## 6.2 Processing Pipeline

- Validate the request — check honeypot field is empty, validate CSRF token, validate form field types and lengths
- Resolve shop by short_code; check shop is active and organisation is enabled
- Check logged-in admin block — reject with 403 if authenticated
- Check IP rate limit (Redis token bucket) — reject with 429 if exceeded
- Validate Turnstile token by calling Cloudflare's verify endpoint — reject with friendly error if invalid
- Run OpenAI Moderation pass on (feedback + name) text — reject if overall flagged; tag with moderation_flagged if specific categories exceed threshold
- Persist the Review record with source=REVIEWBEE, all submission_metadata, moderation flags, enrichment_status=PENDING
- Enqueue Celery enrichment task (enrich_review_task) onto the ai-enrichment queue (same task as Google reviews — see Phase 3b-i)
- Send response to client — redirect to thank-you page
- Dispatch new_review notification (see §10)
- Write audit log entry: { event: "reviewbee.review.submitted", shop_id, review_id, ... }

## 6.3 Idempotency

Duplicate submissions (e.g., user double-taps the Submit button) must not create duplicate Review rows.

### Mechanism

- On form display, a unique submission_token (UUID) is embedded as a hidden field
- On POST, the token is recorded in Redis at lock:reviewbee_submission:{token} with a 5-minute TTL using SET NX (set-if-not-exists)
- If the SET NX fails (token already used), return the existing review's thank-you state instead of creating a new row
- After 5 minutes, the token expires; subsequent POSTs with the same token would create a new Review (this only matters if a user keeps the form open for >5 min and submits again, which is acceptable behavior)

## 6.4 Review Persistence

ReviewBee submissions create Review rows in the same Review table as Google reviews. The source field distinguishes them.

### Review Field Mapping

| **Review Field** | **Value for ReviewBee Submission** |
| --- | --- |
| organisation_id | shop.organisation_id |
| shop_id | shop.id |
| source | REVIEWBEE |
| google_review_id | NULL (no Google ID for direct submissions) |
| reviewer_name | Form input or NULL if blank |
| reviewer_email | Form input or NULL if blank (new field, see §11.1) |
| reviewer_avatar_url | NULL |
| rating | 1–5 from form |
| text | Feedback text from form |
| review_created_at | Server timestamp at submission |
| review_updated_at | Same as review_created_at initially |
| enrichment_status | PENDING (will be processed by Celery) |
| moderation_flagged | From §5.5 |
| moderation_reasons | From §5.5 |
| submission_metadata | JSONB with IP, user agent, referer, etc. (see §5.8) |

## 6.5 AI Enrichment for ReviewBee Reviews

ReviewBee reviews are enriched by the same Phase 3b-i pipeline. The Celery task enrich_review_task is queue-agnostic about the source — it processes any review with enrichment_status=PENDING.

### Prompt Updates

- The prompt template includes the source field so GPT can apply slightly different reasoning if needed
- For ReviewBee submissions, the prompt notes: "This is a direct submission via the store's QR code, not a Google review. The reviewer may be more candid or specific."
- All other prompt structure (combined sentiment + tags + action items, scope detection, JSON schema) is unchanged
- AiUsageLog records the request_type as REVIEW_ENRICHMENT (same as before) — the Review's source field provides the breakdown

## 6.6 Thank-You Page

**Route:** /r/{short_code}/thanks

**Access:** Public; renders only after a successful submission redirect

### Layout

- Centered card with success icon (green check)
- Heading: "Thank you for your review!"
- Body: "Your feedback has been shared with {Shop Name}."
- If the customer provided an email: "If the store replies, we'll send a copy to {customer_email_partially_masked}." (e.g., j****@example.com)

### Google Review Cross-Posting CTA

Below the thank-you message, a secondary card prompts the customer to also leave a Google review. This is genuinely useful for the store and costs the platform nothing.

- Card title: "Help us reach more customers"
- Body: "If you enjoyed your visit, would you also share your review on Google?"
- Primary button: "Leave a Google review →"
- Button links to the Google Maps deep-link for the shop's google_place_id: https://search.google.com/local/writereview?placeid={google_place_id}
- If the shop is connected via the manual fallback path (no Google Place ID required for some shops), the button is hidden
- Optional dismissive link: "No thanks" — closes the card, leaves the thank-you message visible

### Footer

- "Powered by ReviewBee" link
- "Visit ReviewBee" link to https://reviewbee.in (gives the platform a chance to acquire customers organically)

# 7. Reviews Page Updates

## 7.1 New Source Filter

A new filter is added to the Reviews page filter bar (Phase 3a-ii §6.2).

### Filter

- Label: "Source"
- Type: Dropdown
- Default: All Sources
- Options: All Sources, Google, ReviewBee
- URL parameter: source (e.g., /admin/org/reviews/?source=reviewbee)

### Filter Bar Position

The filter bar already contains: Store, Rating, Sentiment, Reply Status, From Date, To Date, Search. The new Source filter is placed between Store and Rating to keep similar-purpose filters grouped.

## 7.2 Source Badge on Each Review Card

Each review card in the list shows a small badge indicating the source. The badge is positioned near the existing sentiment and tag chips.

### Google Source Badge

- Background: light gray
- Icon: Google G icon
- Label: "Google"

### ReviewBee Source Badge

- Background: soft yellow
- Icon: bee icon (custom or Lucide alternative)
- Label: "ReviewBee"

## 7.3 Per-Card Field Differences

The review card layout from Phase 3 §6.3 is largely unchanged. A few field-level adjustments handle the source differences.

### Reviewer Name Display

- Google: shows reviewer_name as provided by Google
- ReviewBee with name: shows the provided name
- ReviewBee anonymous (no name): shows "Anonymous" in italics

### Reviewer Email Indicator (ReviewBee Only)

- If the ReviewBee submission included an email: small mail icon next to the reviewer name with tooltip "Customer provided email — replies are sent by email"
- If no email: no icon
- The actual email is NOT displayed inline (privacy); it appears only in the reply composer if the user clicks Reply

### Moderation Flag Indicator

- If moderation_flagged is true on a Review (only possible for ReviewBee — Google reviews are never moderation-flagged): small amber warning icon next to the source badge with tooltip "Flagged for review — automatic moderation found potential issues"
- Hovering the badge reveals the moderation_reasons list
- Flagged reviews still appear in the list (they are not auto-hidden) — the indicator just signals "this might warrant a closer look"

## 7.4 Reply UI Differences

The Phase 3a-ii reply UI (inline expansion, comment-to-post pattern) is mostly the same for ReviewBee, with a few differences.

### Google Review Reply

- Inline composer; on submit, posts to Google synchronously
- Confirmation: "Replied on {date}" once posted

### ReviewBee Review Reply (with email)

- Inline composer renders identically to Google reply composer
- Above the composer, helper text: "Your reply will be emailed to {customer_email_partially_masked}"
- On submit, sends an email via Amazon SES (see §8) and stores a ReviewReply row
- Confirmation: "Reply sent on {date}" instead of "Replied on {date}"

### ReviewBee Review Reply (without email)

- Reply button is hidden
- In place of the button: helper text "This customer didn't provide an email, so a reply isn't possible."

# 8. Email Reply Flow

## 8.1 Overview

When a Manager or Org Admin submits a reply to a ReviewBee review where the customer provided an email, the system sends an email to the customer via Amazon SES (Phase 1 §15). Replies are one-shot — the customer cannot reply back through the platform in Phase 5.

## 8.2 Endpoint

**Method:** POST

**Path:** /api/v1/reviews/{review_id}/reply/

**Permission:** User must have reply permission for the review's shop (Phase 3a-ii §6.5)

**Body:** { "text": "<reply text>" }

## 8.3 Processing

- Validate that the review has source=REVIEWBEE and reviewer_email is not null
- Validate the reply text (1–4000 chars; matches Google's limit for consistency)
- Persist a ReviewReply row with status=POSTED, posted_by_user_id, text, posted_at
- Send email synchronously via send_transactional_email (Phase 1 §15.4) to reviewer_email
- If email send fails, the ReviewReply row is rolled back (transaction.atomic), the user gets an error toast
- On success, return 201 with the new ReviewReply payload
- Audit log entry: { event: "reviewbee.reply.sent", review_id, reply_id, recipient_email_hash }

## 8.4 Email Template

**Template name:** emails/reviewbee_reply

**Subject:** {Shop Name} replied to your review

### Body Outline

- Greeting: "Hi {customer_name}" (or "Hello" if anonymous)
- Brief intro: "Thank you for your review of {Shop Name} on {review_date}. Here's their reply:"
- Reply text in a quoted/highlighted block (preserve customer's reply formatting)
- Below the reply: a small box showing the customer's original review (rating + first 200 chars of feedback) for context
- Closing: "If you'd like to share your experience with more customers, leave a Google review →" (deep-link if google_place_id available)
- Footer with ReviewBee branding and unsubscribe link (one-click suppression)

## 8.5 Email Suppression Handling

- If the recipient's email is on the suppression list (from Phase 1 §15.7 — bounces, complaints), the email is NOT sent and the user gets an error toast: "This email address has been suppressed and cannot receive replies."
- The ReviewReply row is still rolled back in this case
- Recommendation in the error toast: "You can still note your reply internally by adding a note to the action item." (forward-looking — Action Items module from Phase 3b-ii supports notes)

# 9. Dashboard Updates

Phase 4 (the dashboard) was built before Phase 5. With ReviewBee submissions now flowing into the same Review table, the dashboard must be updated so users can distinguish between Google and ReviewBee data when desired.

## 9.1 New Source Filter

A new Source filter is added to the dashboard filter bar (Phase 4 §4).

### Filter

- Label: "Source"
- Type: Dropdown
- Default: All Sources
- Options: All Sources, Google, ReviewBee
- URL parameter: source
- Position: in the filter bar after Date Range, before Clear Filters

## 9.2 Per-Widget Behavior

Every widget on the dashboard respects the Source filter. The same Source filter applies to all widgets simultaneously — there is no per-widget filter.

| **Widget** | **Effect of Source Filter** |
| --- | --- |
| Top Performing Outlets (bar chart) | Average rating computed from reviews of selected source(s) only |
| Performance Highlights card | Top/bottom shop selection considers only reviews of selected source(s) |
| "Your Store" card (single-shop) | All metrics filtered to selected source(s); trend calculation uses same source filter for both periods |
| Total Reviews KPI | Counts reviews of selected source(s) |
| Average Rating KPI | Averages reviews of selected source(s) |
| Negative Reviews KPI | Counts negative-sentiment reviews of selected source(s) |
| Sentiment Distribution donut | Distribution computed from reviews of selected source(s) — coverage footer reflects enriched-vs-total within the selected source(s) |

## 9.3 Filter Scope Rule (from Phase 4 §3.3) Still Applies

- Top Performing Outlets section (bar chart + Performance Highlights) uses Date Range and Source filters only — Region and Store filters do NOT apply, by design
- KPI cards and Sentiment Distribution use the full filter set (Region + Store + Date + Source)

## 9.4 Endpoint Updates

All five Phase 4 dashboard endpoints accept an optional source query parameter.

- GET /api/v1/dashboard/top-performing/?source=…
- GET /api/v1/dashboard/highlights/?source=…
- GET /api/v1/dashboard/your-store/?source=…
- GET /api/v1/dashboard/kpis/?source=…
- GET /api/v1/dashboard/sentiment-distribution/?source=…

### Parameter Values

- Omitted or empty → All Sources (no filter)
- source=google → only reviews where source=GOOGLE
- source=reviewbee → only reviews where source=REVIEWBEE
- Any other value → 400 Bad Request

## 9.5 Cache Key Updates

The dashboard cache key format from Phase 4 §9.3 now includes source in the filter hash.

dashboard:{endpoint}:{org_id}:{user_id}:{filter_hash}

filter_hash now incorporates: (region, store, range, from, to, source, accessible_shop_ids). Existing cache entries from before Phase 5 deployment will simply expire on their 5-minute TTL — no manual flush needed.

# 10. Notification Updates

## 10.1 New-Review Notification Includes Source

The new_review notification (Phase 3b-ii §8.6) is dispatched for both Google and ReviewBee reviews. The notification's payload now includes the source so the bell popover can show a source indicator.

### Updated Payload Schema

{

"review_id": "<uuid>",

"shop_id": "<uuid>",

"shop_name": "<string>",

"reviewer_name": "<string|null>",

"rating": <int>,

"source": "GOOGLE" | "REVIEWBEE",

"text_preview": "<first 100 chars>"

}

## 10.2 Bell Popover Display

- Each notification row in the popover shows a small source badge next to the timestamp
- Google: small G icon (gray)
- ReviewBee: small bee icon (yellow)
- Click on a notification navigates to the Reviews page filtered to that review (existing behavior, unchanged)

## 10.3 Recipients

Recipient rules from Phase 3b-ii §8.6 are unchanged:

- Org Admin and any Manager — receive notifications for all new reviews in the organisation
- Staff — receive notifications only for reviews of shops in their access scope
- This applies equally to Google and ReviewBee notifications

## 10.4 Counter Computation

The unread counter (Phase 3 §13.6) treats Google and ReviewBee notifications identically. The 60-second HTTP poll for the counter does not differentiate.

# 11. Data Model Updates

## 11.1 Review Model Updates

New fields added to the existing Review model:

- source — Enum, NOT NULL. Values: GOOGLE | REVIEWBEE. Default: GOOGLE for backfill.
- reviewer_email — String, nullable. Max 254 chars (RFC 5321). Only set for ReviewBee submissions where the customer provided an email.
- submission_metadata — JSONB, nullable. Captures IP address, user agent, referer, anti-abuse layer results for ReviewBee submissions. NULL for Google reviews.
- moderation_flagged — Boolean, NOT NULL, default FALSE. Set TRUE when a category-level moderation score exceeds threshold without being overall flagged.
- moderation_reasons — JSONB, nullable. Array of category names (e.g., ["harassment", "violence"]) when flagged.

### New Indexes

- (organisation_id, source, review_created_at) — supports source-filtered queries on Reviews list and dashboard
- (shop_id, source, review_created_at) — supports per-shop source-filtered queries

### Updates to Existing Constraints

- Unique constraint (shop_id, google_review_id) is now conditional: applies only when source=GOOGLE. Postgres partial unique index: WHERE google_review_id IS NOT NULL
- ReviewBee submissions have google_review_id IS NULL, so the constraint doesn't apply to them

## 11.2 Shop Model Updates

- short_code — String, 8 chars, NOT NULL after migration completes. Unique across the platform.
- Unique index on short_code

## 11.3 New Model — SubmissionRejectionLog

Captures rejected submission attempts for manual investigation. Distinct from the audit log, which captures successful events.

### Fields

- id (PK, UUID)
- shop_id (FK to Shop, indexed)
- rejection_reason — Enum: HONEYPOT_TRIPPED | RATE_LIMIT_EXCEEDED | TURNSTILE_FAILED | MODERATION_REJECTED | ADMIN_BLOCKED | INVALID_FORM
- ip_address (string)
- user_agent (string)
- referer (string, nullable)
- submitted_form_snapshot — JSONB capturing the partially-validated form fields (excluding turnstile token, honeypot)
- created_at
- Index: (shop_id, created_at)

### Retention

- 90 days; older rows are purged by a Celery Beat task

## 11.4 Audit Log Additions

New audit actions for Phase 5:

- reviewbee.review.submitted
- reviewbee.review.rejected
- reviewbee.reply.sent
- reviewbee.reply.failed
- shop.short_code.generated
- shop.qr.downloaded — when an admin downloads a QR code (PNG or PDF)
- moderation.call — every OpenAI Moderation API call, success or failure

# 12. Technical Design

Phase 5 follows the conventions in CLAUDE.md (services and selectors pattern, Celery for background work, Redis for rate limiting and caching, etc.). This section documents Phase 5 specifics.

## 12.1 New App — apps/reviewbee/

A new Django app houses the public submission flow and ReviewBee-specific logic that doesn't naturally belong in apps/reviews/ (which remains the Google-focused module).

### Module Layout

- apps/reviewbee/views.py — public form GET and POST handlers, thank-you page handler, error pages
- apps/reviewbee/services/submission.py — submission processing pipeline (validation → moderation → persistence)
- apps/reviewbee/services/moderation.py — OpenAI Moderation API wrapper
- apps/reviewbee/services/qr_codes.py — QR card generation (PNG + PDF) and GCS caching
- apps/reviewbee/services/short_codes.py — short code generation with collision check
- apps/reviewbee/services/turnstile.py — Cloudflare Turnstile verification
- apps/reviewbee/services/email_reply.py — SES email send for ReviewBee replies
- apps/reviewbee/selectors/submission_logs.py — read primitives for SubmissionRejectionLog
- apps/reviewbee/templates/reviewbee/ — public submission templates (form, thank-you, errors)
- apps/reviewbee/static/reviewbee/ — public submission CSS, no admin styles

## 12.2 Updates to Existing Apps

### apps/stores/

- Add short_code field to Shop model
- Migration generates short_code for existing shops
- New service short_code service called on shop creation hook

### apps/reviews/

- Add source, reviewer_email, submission_metadata, moderation_flagged, moderation_reasons fields to Review model
- Add new indexes (§11.1)
- Update existing reply service to detect source=REVIEWBEE and route to email send instead of Google API
- Update review serializers to include source and the new fields where appropriate

### apps/dashboard/

- Add source query parameter to all dashboard endpoints
- Update cache key format to include source in the filter hash
- Update aggregation selectors to filter by source when provided

## 12.3 API Endpoints

| **Method + Path** | **Purpose** | **Permissions** |
| --- | --- | --- |
| GET /r/{short_code} | Render public submission form | Public |
| POST /r/{short_code} | Submit a ReviewBee review | Public; rate-limited; Turnstile-validated |
| GET /r/{short_code}/thanks | Thank-you page after successful submission | Public; redirected after POST |
| GET /api/v1/shops/{shop_id}/qr/?format=png\|pdf | Download QR card image | Org Admin / Manager / Staff with shop access |
| GET /api/v1/reviews/?source=… | Reviews list filtered by source (existing endpoint, new param) | Existing Phase 3 permissions |
| GET /api/v1/dashboard/*?source=… | All dashboard endpoints (existing endpoints, new param) | Existing Phase 4 permissions |
| POST /api/v1/reviews/{id}/reply/ | Reply to review — routes to Google or email based on source (existing endpoint, internal logic update) | Existing Phase 3 permissions |

## 12.4 Settings Additions

# config/settings/base.py

# Public-facing

PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="https://app.reviewbee.in")

# Cloudflare Turnstile

TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY")

TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY")

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# OpenAI Moderation

OPENAI_MODERATION_MODEL = env("OPENAI_MODERATION_MODEL", default="omni-moderation-latest")

OPENAI_MODERATION_FLAG_THRESHOLD = env.float("OPENAI_MODERATION_FLAG_THRESHOLD", default=0.5)

# ReviewBee submission limits

REVIEWBEE_RATE_LIMIT_PER_IP_PER_SHOP = env.int("REVIEWBEE_RATE_LIMIT_PER_IP_PER_SHOP", default=5)

REVIEWBEE_RATE_LIMIT_WINDOW_SECONDS = env.int("REVIEWBEE_RATE_LIMIT_WINDOW_SECONDS", default=86400)

# QR code

QR_CARD_VERSION = "v1"

QR_CACHE_BUCKET = env("QR_CACHE_BUCKET", default="reviewbee-qr-codes")

## 12.5 New Dependencies

[project.dependencies]

qrcode = "^7.4.0" # QR code generation

Pillow = "^11.0.0" # PNG card composition

reportlab = "^4.2.0" # PDF generation

# Cloudflare Turnstile uses HTTP requests via requests library (already a dependency via tenacity etc.)

## 12.6 Query Optimisation

- Reviews list endpoint with source filter must use the new (organisation_id, source, review_created_at) index — verify with EXPLAIN ANALYZE
- Dashboard endpoints with source filter use the same indexes; add a CaptureQueriesContext test asserting that source filtering does not increase query count
- Public submission form GET is highly cacheable — cache the rendered template at the CDN level for 5 minutes (Cache-Control: public, max-age=300, stale-while-revalidate=60)
- Submission POST is not cached

## 12.7 Performance Targets

- Public submission form page load (TTFB): under 200ms at p95
- Submission POST end-to-end: under 1.5 seconds at p95 (includes Turnstile verify ~150ms + Moderation ~200ms + DB write + email enqueue)
- QR PNG generation (cold): under 800ms at p95
- QR PDF generation (cold): under 1.5 seconds at p95
- QR download (cached): under 100ms at p95 (signed URL redirect)

# 13. Phase 5 Acceptance Criteria

## 13.1 Branding

- "ReviewBee" wordmark replaces all "BrandName" placeholders in admin UI, login, sidebar, emails.
- Public submission page header shows "ReviewBee · {Organisation Name}".
- All transactional emails use the [ReviewBee] subject prefix and ReviewBee footer.

## 13.2 Short Codes and QR Generation

- Every shop has a unique short_code; a backfill migration generates codes for shops created before Phase 5.
- Short codes follow the format rules (8 chars, lowercase alphanumeric, excluding ambiguous characters) and are immutable.
- Shop creation flow auto-generates a short_code; collision is retried up to 5 times.
- QR PNG (600×800) and PDF (A6) are generated on demand and cached in GCS for instant subsequent downloads.
- QR download is available inline on Shop Details and via a quick action on the Shops list row.
- Audit log records every QR download with format and shop ID.

## 13.3 Public Submission Page

- GET /r/{short_code} resolves to the correct shop, returns 404 for invalid codes, 410 for inactive shops or disabled organisations.
- Form renders with all fields, helper text, Turnstile widget, and ReviewBee+org co-branding.
- Mobile-first layout works correctly on phones, tablets, and desktops.
- Logged-in admin users see the warning banner; submit is disabled UI-side and rejected server-side.
- All form states render correctly: default, submitting, already-submitted-today (localStorage), rate-limited, moderation-rejected, network error, success.
- Successful submission redirects to the thank-you page with the Google review CTA (if google_place_id is set).
- CSRF protection works for anonymous submissions.

## 13.4 Anti-Abuse Layers

- Honeypot field rejects bots that fill all visible inputs.
- localStorage marker prevents repeat submissions from the same browser within 24 hours.
- Soft IP rate limit allows up to 5 successful submissions per shop per IP per 24 hours; subsequent submissions return 429 with friendly message.
- Cloudflare Turnstile token is validated server-side; missing or invalid tokens reject the submission.
- OpenAI Moderation rejects flagged content; sub-threshold flags persist with moderation_flagged=true and moderation_reasons populated.
- Logged-in admin block returns 403 server-side regardless of UI state.
- Every rejected submission writes to SubmissionRejectionLog with the rejection_reason.
- Every successful submission's submission_metadata captures IP, user agent, referer, and anti-abuse layer results.

## 13.5 Storage and Enrichment

- ReviewBee submissions create Review rows with source=REVIEWBEE, google_review_id=NULL, and the new field set populated.
- Conditional unique constraint on (shop_id, google_review_id) does not block ReviewBee submissions (which have NULL google_review_id).
- AI enrichment Celery task processes ReviewBee reviews exactly like Google reviews (same task, same idempotency, same cost tracking).
- Moderation pre-pass adds 100–300ms latency on submission and is logged in AuditLog.
- Concurrent duplicate submissions (e.g., double-click) result in only one Review row due to the submission_token idempotency mechanism.

## 13.6 Reviews Page

- New Source filter dropdown appears in the filter bar with options All Sources / Google / ReviewBee.
- Each review card shows a source badge (Google or ReviewBee).
- ReviewBee reviews show "Anonymous" in italics when no name is provided.
- ReviewBee reviews with email show a small mail icon next to the reviewer name.
- Moderation-flagged reviews show a small amber warning icon with hover tooltip.
- Reply UI for ReviewBee reviews with email opens an inline composer; on submit, sends an email via SES.
- Reply UI is hidden for ReviewBee reviews without an email.
- Email reply confirmation shows "Reply sent on {date}" instead of "Replied on {date}".

## 13.7 Email Reply

- Email is sent via Amazon SES (Phase 1 §15) using the reviewbee_reply template.
- Email subject: "{Shop Name} replied to your review".
- Email body includes the reply text, original review excerpt, and a Google review CTA when available.
- Suppressed emails (bounced/complained) reject the reply with a clear toast; the ReviewReply row is rolled back.
- Failed email send rolls back the ReviewReply row in the same transaction.

## 13.8 Dashboard Updates

- New Source filter dropdown is added to the dashboard filter bar.
- All five dashboard endpoints accept source query parameter and return correctly filtered data.
- Cache keys include source so different filter selections don't collide.
- URL state preserves source on share/reload.
- Phase 4 acceptance criteria continue to pass after Phase 5 changes.

## 13.9 Notifications

- New ReviewBee review fires the same new_review notification with source=REVIEWBEE in payload.
- Bell popover shows source badge on each notification row.
- Recipient rules (Org Admin/Manager always; Staff for accessible shops only) work identically for both sources.

## 13.10 Cross-Cutting

- All routes added in Phase 5 enforce role + tenant scoping at the permission layer.
- Public submission routes (/r/*) are explicitly opted into the public namespace and do NOT enforce authentication.
- All forms enforce the validation rules in this document.
- Public page is responsive at mobile/tablet/desktop breakpoints; mobile is the primary experience.
- Every list endpoint with the new source filter has a CaptureQueriesContext test asserting query-count ceiling holds with the filter active.
- Sentry receives errors from public submission flow as well as admin flow.
- All audit log events listed in §11.4 are written and queryable.
- CLAUDE.md is updated to document Turnstile integration, ReviewBee app structure, and the source field convention.

# 14. Risks and Mitigations

| **Risk** | **Mitigation** |
| --- | --- |
| Public submission abused at scale despite layered defense | Six-layer strategy designed precisely for this; extensive logging via SubmissionRejectionLog enables manual investigation and pattern detection. If a specific shop is targeted, support can review logs and add per-shop blocks (future feature). |
| Real customers blocked by rate limit on shared networks | Soft limit (5/IP/shop/24h) is permissive enough for typical shared-network scenarios. localStorage marker provides client-side helpful state instead of server rejection for repeat-from-same-browser cases. |
| Cloudflare Turnstile down or rate limited | Failure mode is fail-closed (rejects submission with retry message). Cloudflare's SLA is high; brief outages would temporarily reject submissions but not corrupt data. |
| Org Admin self-reviews to game metrics | Logged-in admin block prevents the trivial case. Sophisticated abuse (incognito browsing, multiple accounts) is logged in submission_metadata for later investigation. Dashboard exposes ReviewBee vs Google split so abuse is partially transparent. |
| Email replies bounce or fail silently | SES bounce/complaint webhooks (Phase 1 §15.7) suppress addresses; the reply UI tells the user when an email is suppressed. Audit log captures every send attempt. |
| GPT moderation false positives reject legitimate reviews | Threshold-based behavior — only overall flagged rejects; sub-threshold persists with flag for the store to review. Moderation API is free, so threshold tuning has no cost implication. |
| Customers don't realize the reply was sent by email | Thank-you page tells them: "If the store replies, we'll send a copy to {email}." Clear expectations set. |
| Print-quality PDF doesn't render correctly on certain printers | Use a well-tested PDF library (reportlab) with embedded fonts. Manual visual QA on at least 3 different printer drivers before shipping. |
| Short code collisions in extremely large deployments | 32-char alphabet × 8 chars = ~10^11 codes. Collision check at generation. Even with 1M shops, collision probability is negligible. |
| Dashboard performance degrades with the new source index | New indexes are partial (where source IS NOT NULL not relevant — source is NOT NULL by design). EXPLAIN ANALYZE on representative datasets confirms index usage. Cache layer absorbs repeat queries. |
| Customer email captured but not used for reply for weeks | GDPR/privacy: store the email; document retention rules. Consider future feature to auto-delete unused customer emails after N days. Out of scope for Phase 5 but flagged. |
