**REQUIREMENTS DOCUMENT**

Multi-Tenant Review Management Platform

**Phase 1 — Superadmin Module**

Version 1.0 • April 2026

# 1. Document Overview

This document specifies the functional, non-functional, UI, and technical requirements for a multi-tenant SaaS platform that manages organisations, their stores, and Google Business Profile reviews. The platform supports three user roles — Superadmin, Organisation Admin, and Staff Admin.

This version of the document defines Phase 1 scope — the Superadmin module and its supporting invitation flow — in full detail. Later phases for Organisation Admin, Staff Admin, and Review management are outlined at a high level and will be detailed in subsequent document versions.

## 1.1 Phase 1 Scope

- Superadmin authentication and dashboard
- Organisation list with search, filter, and pagination
- Create, edit, view, enable, disable, and delete organisations
- Adjust store allocation per organisation
- Organisation Admin invitation email flow
- Organisation Admin account activation page
- Superadmin profile management
- Global design system, left sidebar layout, and responsive behaviour

## 1.2 Out of Scope for Phase 1

- Organisation Admin dashboard and store management
- Staff Admin role and its dashboard
- Google Business Profile OAuth connection
- Review fetching, storage, and analytics
- Billing, subscription, and plan selection
- Notifications module beyond basic email

# 2. User Roles Overview

The platform defines three user roles with strict role-based access control. Each role has its own dashboard, sidebar, and permitted operations.

| **Role** | **Primary Responsibility** | **Created By** | **Phase** |
| --- | --- | --- | --- |
| Superadmin | Platform-level administration; manages all organisations and store allocations | System / seed data | Phase 1 |
| Organisation Admin | Manages one organisation; creates stores, connects Google Business Profile, invites Staff Admins | Superadmin (via email invitation on organisation creation) | Phase 2 |
| Staff Admin | Manages one or more specific stores under an organisation; views and responds to reviews | Organisation Admin (via email invitation) | Phase 3 |

# 3. Branding and Design System

## 3.1 Brand Colours

| **Token** | **Hex** | **Usage** |
| --- | --- | --- |
| Primary Yellow | #FACC15 | Primary buttons, active states, accent highlights, brand elements |
| Accent Yellow | #EAB308 | Hover state on primary buttons |
| Soft Yellow | #FEFCE8 | Light background accents, hover tints on list rows |
| Primary Black | #0A0A0A | Sidebar background, primary text, headings |
| Neutral Gray | #525252 | Secondary text, helper text, metadata |
| Border Gray | #E5E5E5 | Dividers, table borders, input borders |
| Background Gray | #FAFAFA | Main content area background |
| Success Green | #16A34A | Active status badges, success toasts |
| Error Red | #DC2626 | Destructive buttons, error toasts, delete confirmations |
| Warning Amber | #F59E0B | Warning messages, caution states |
| Info Blue | #2563EB | Info toasts, informational tooltips |

## 3.2 Typography

- Primary font family: Inter (fallback: system sans-serif)
- Headings are bold with clear visual hierarchy; body text remains regular weight
- Minimum body size: 14px; recommended 15–16px for readability

## 3.3 Visual Style

- Clean, modern SaaS dashboard aesthetic inspired by Linear, Stripe, and Vercel
- Subtle rounded corners (6–8px radius)
- Generous whitespace and clear content hierarchy
- Icons use a single-line style (lucide-style line icons)
- No emojis in the UI

## 3.4 Logo

Logo design is pending. During Phase 1 development a text placeholder reading “BrandName” is used in the sidebar header, rendered in yellow on black. The final logo will replace the placeholder without structural changes.

# 4. Global UI and UX Requirements

These requirements apply to every page, every role, and every breakpoint. They define the overall shell within which each role-specific module renders.

## 4.1 Layout Shell

### Left Sidebar (fixed on desktop)

- Background: Primary Black
- Width: approximately 240px on desktop
- Header area shows the logo placeholder in yellow on black
- Menu items display as white text; hover shows yellow text; active item has a yellow left border and yellow text
- Menu is role-specific — Superadmin, Organisation Admin, and Staff Admin each see their own menu set
- Logout menu item is pinned to the bottom of the sidebar

### Top Bar

- Background: white with a subtle bottom border in Border Gray
- Left side: current page title or breadcrumb
- Right side: notification bell icon (red dot if unread), profile avatar with dropdown (Profile, Logout)

### Main Content Area

- Background: Background Gray
- Generous inner padding
- Content blocks (cards, tables, forms) use white backgrounds on top of the gray canvas

## 4.2 Responsive Behaviour

| **Breakpoint** | **Behaviour** |
| --- | --- |
| Desktop (≥ 1024px) | Full sidebar, multi-column layouts, full-width tables |
| Tablet (768–1023px) | Collapsible icon-only sidebar rail, tables scroll horizontally when needed, condensed spacing |
| Mobile (< 768px) | Hamburger drawer replaces sidebar; tables transform into stacked cards (label left, value right); modals expand to full-screen; filter bars stack vertically |

## 4.3 Reusable Components

- Button variants: Primary (yellow bg, black text), Secondary (white bg, black border), Danger (red bg, white text), Ghost (transparent with hover tint)
- Form inputs, selects, and textareas with a label above, optional helper text below, and red border + error message on invalid input
- Modal dialogs with overlay background dimming and a close (×) button top-right
- Confirmation popups — smaller modal variant with an icon, title, message, and two buttons
- Toast notifications — top-right, auto-dismiss, colour-coded by type (success, error, warning, info)
- Data tables with sticky headers, row hover highlighting, and a three-dot menu per row for actions
- Status badges (pill shape, colour-coded)
- Empty states — centred icon, primary message, and optional CTA button
- Loading states — skeleton placeholders for tables, spinners inside buttons during submit

## 4.4 Accessibility

- Full keyboard navigation across all interactive elements
- Visible focus states on buttons, links, and form fields
- ARIA labels on icon-only buttons
- Focus trap within open modals
- Minimum WCAG AA colour contrast, with special attention to yellow buttons with black text
- Logical heading hierarchy on every page

## 4.5 Feedback and Confirmations

- Every sensitive or destructive action (disable, enable, delete, store count change, resend invitation) requires a confirmation popup
- Delete actions require a type-to-confirm pattern where the user types the entity name before the Delete button is enabled
- Every successful mutation shows a success toast
- Every failed mutation shows an error toast with a human-readable message

# 5. Superadmin Module (Phase 1)

The Superadmin is the top-level platform administrator. They create and manage organisations, allocate store slots, and resend admin invitations. This section specifies every page, modal, and confirmation popup in detail so the UI can be implemented directly from this specification.

## 5.1 Sidebar Menu (Superadmin)

- Organisations (Building icon) — default landing page
- Profile (User icon)
- Logout (Logout icon, bottom-pinned)

## 5.2 Login Page

**Route:** /login

**Access:** Public

**Layout:** Centred, no sidebar. Optional split layout: left panel in yellow/black with brand mark, right panel with the login form.

### Fields

| **Field** | **Type** | **Required** | **Validation** |
| --- | --- | --- | --- |
| Email | Email input | Yes | Valid email format |
| Password | Password input with show/hide toggle | Yes | Cannot be empty |

### Actions

- Primary button: “Sign In” (full-width, yellow)
- Link: “Forgot password?” (right-aligned below password)

### States

- Default
- Loading (spinner inside the Sign In button while submitting)
- Error — inline message above the form on invalid credentials

## 5.3 Organisations List Page

**Route:** /admin/organisations

**Access:** Superadmin only

**Page title:** Organisations

**Default landing:** Yes — Superadmin lands here after login

### Header Area

- Page title: “Organisations”
- Top-right primary action: “+ Create Organisation” button

### Filter Bar

- Search input with magnifying glass icon — placeholder: “Search by name or email”. Searches the Name and Email columns.
- Status filter dropdown with options: All, Active, Disabled
- Type filter dropdown with options: All, Retail, Restaurant, Pharmacy, Supermarket

### Table Columns

| **Column** | **Display** |
| --- | --- |
| Name | Bold text; clickable — opens the Organisation Details modal |
| Type | Badge (neutral colour) |
| Email | Plain text |
| # Stores | Format: “X / Y” (used / allocated) |
| Status | Badge — green “Active” or gray “Disabled” |
| Created Date | Format: MMM DD, YYYY |
| Actions | Three-dot menu with row actions |

### Row Actions Menu

- View Details
- Edit
- Adjust Store Count
- Enable / Disable (label toggles based on current status)
- Resend Invitation (visible only if the Org Admin has not yet activated the account)
- Delete

### Pagination

- Bottom-right area
- Display: “Showing X–Y of Z”
- Rows-per-page selector with options: 10, 25, 50, 100 (default 10)
- Page navigation controls: first, previous, next, last

### Empty State

- Centred Building icon
- Primary message: “No organisations yet”
- CTA button: “Create your first organisation”

### Loading State

- Skeleton rows in the table area while data loads

## 5.4 Create Organisation Modal

**Trigger:** “+ Create Organisation” button on the Organisations List page

**Title:** Create New Organisation

**Subtitle:** Enter the organisation details to get started.

### Fields

| **Field** | **Type** | **Required** | **Validation** | **Placeholder** |
| --- | --- | --- | --- | --- |
| Organisation Name | Text input | Yes | 2–100 characters | e.g., Example Corp |
| Organisation Type | Dropdown | Yes | One of: Retail, Restaurant, Pharmacy, Supermarket | Select organisation type |
| Address | Textarea | No | Maximum 500 characters | e.g., 123 Main St, City, State, ZIP |
| Email | Email input | Yes | Valid email format; must be unique across organisations | e.g., contact@example.com |
| Number of Stores | Number input | Yes | Integer, minimum 1, maximum 1000 | e.g., 5 |

### Footer Buttons

- Cancel (secondary, left) — closes the modal without saving
- Save (primary, right) — submits the form

### Success Behaviour

- Modal closes
- Toast appears (top-right): “Organisation created. Invitation email sent to {email}.”
- Organisations list refreshes and shows the new row
- System generates a secure invitation token valid for 48 hours and sends an activation email to the provided email address

## 5.5 Organisation Details Modal

**Trigger:** Clicking the organisation name in the table, or selecting “View Details” from the row actions menu

**Title:** The organisation's name

**Layout:** Read-only details shown in a two-column labelled grid

### Information Displayed

- Name
- Type (badge)
- Address
- Email
- Stores: X used of Y allocated
- Status (badge — Active or Disabled)
- Created Date
- Org Admin activation status: Pending invite, Active, or Invitation expired
- Timestamp of the last invitation sent

### Footer Buttons

- Resend Invitation (secondary) — visible only if the Org Admin has not yet activated
- Edit (secondary) — opens the Edit Organisation modal
- Close (primary) — closes the modal

## 5.6 Edit Organisation Modal

The Edit modal reuses the same form layout as the Create modal, with all fields pre-filled from the current organisation record.

### Field Differences from Create

- Email field is disabled and cannot be changed after creation
- All other fields are editable

### Footer Buttons

- Cancel (secondary)
- Save Changes (primary)

### Success Behaviour

- Modal closes
- Toast: “Organisation updated.”
- List or details view refreshes with the new values

## 5.7 Adjust Store Count Modal

**Trigger:** “Adjust Store Count” from the row actions menu

**Title:** Adjust Allocated Stores

### Content

- Display line: “Currently using X of Y stores”
- Input: Number input for the new allocation
- Helper text below input: “Minimum: {current in-use count}”
- If the user enters a value below the current in-use count, an inline amber warning appears: “You cannot set this below the current in-use count.”

### Footer Buttons

- Cancel (secondary)
- Update (primary)

### Flow

- User enters new allocation and clicks Update
- A confirmation popup is shown before applying the change
- On confirm, modal closes and a toast appears: “Store allocation updated to {N}.”

## 5.8 Confirmation Popups

All confirmation popups use the same reusable component: icon, title, message, and two buttons. The variants below define the specific copy and button treatment for each action.

### 5.8.1 Disable Organisation

**Icon:** Warning (amber)

**Title:** Disable Organisation?

**Message:** The organisation '{name}' and all its stores will be inaccessible. You can re-enable it later.

**Buttons:** Cancel / Disable (red)

**Success toast:** Organisation '{name}' disabled.

### 5.8.2 Enable Organisation

**Icon:** Info (blue)

**Title:** Enable Organisation?

**Message:** The organisation '{name}' will regain access.

**Buttons:** Cancel / Enable (primary)

**Success toast:** Organisation '{name}' enabled.

### 5.8.3 Delete Organisation

**Icon:** Alert (red)

**Title:** Delete Organisation?

**Message:** This will permanently delete '{name}' and all associated data. This action cannot be undone.

**Extra control:** Type-to-confirm input with placeholder “Type the organisation name to confirm”

**Buttons:** Cancel / Delete (red, disabled until typed name matches exactly)

**Success toast:** Organisation '{name}' deleted.

### 5.8.4 Resend Invitation

**Icon:** Mail (blue)

**Title:** Resend Invitation?

**Message:** A new invitation link will be sent to {email}. The previous link will be invalidated.

**Buttons:** Cancel / Resend (primary)

**Success toast:** Invitation resent to {email}.

### 5.8.5 Adjust Store Count Confirmation

**Icon:** Info (blue)

**Title:** Update Store Allocation?

**Message:** Store allocation for '{name}' will change from {oldCount} to {newCount}.

**Buttons:** Cancel / Update (primary)

## 5.9 Organisation Admin Invitation Acceptance Page

**Route:** /invite/accept/<token>/

**Access:** Public, token-gated

**Layout:** Centred card, no sidebar — consistent with the Login page treatment

### Purpose

When a Superadmin creates a new organisation, the system emails a secure, time-limited invitation link to the organisation's contact email. The recipient clicks the link, which opens this page and allows them to create their Organisation Admin account.

### Header

- Title: “Welcome to {OrganisationName}”
- Subtitle: “Create your Organisation Admin account to get started.”

### Fields

| **Field** | **Type** | **Required** | **Behaviour** |
| --- | --- | --- | --- |
| Email | Email input | N/A | Pre-filled and disabled — locked to the invitation |
| Full Name | Text input | Yes | 2–100 characters |
| Password | Password input with show/hide toggle | Yes | Django default validators; strength indicator shown below |
| Confirm Password | Password input | Yes | Must match Password exactly |

### Action

- Create Account (primary, full-width button)

### Error Pages

- Invalid or expired token — full-page message: “This invitation link is invalid or has expired. Please contact your administrator to request a new one.”
- Already accepted — full-page message: “This invitation has already been used.”

### Success Behaviour

- Invitation token is marked as used (single-use)
- Organisation Admin user is created and associated with the organisation
- Organisation's Org Admin activation status is updated to Active
- User is automatically logged in and redirected to the Organisation Admin dashboard (Phase 2 scope)

### Security Rules

- Invitation token is a cryptographically secure random string, signed using Django's TimestampSigner
- Token is valid for 48 hours from generation
- Token is single-use — invalidated immediately after successful activation
- Resending a new invitation invalidates any previously generated token for the same organisation
- Password must pass all Django default validators (minimum length, not too common, not entirely numeric, not similar to user attributes)
- All invitation links use HTTPS only
- An audit log entry is created for every invitation sent, accepted, expired, and resent

## 5.10 Profile Page

**Route:** /admin/profile

**Access:** Superadmin (and in future phases, Org Admin and Staff Admin using their own profile route)

**Layout:** Two sections as separate cards within the main content area

### Profile Information Card

- Field: Full Name (editable text input)
- Field: Email (read-only)
- Action: Save Changes (primary button)
- Success toast: “Profile updated.”

### Change Password Card

- Field: Current Password (required)
- Field: New Password (required, with strength indicator)
- Field: Confirm New Password (required, must match New Password)
- Action: Update Password (primary button)
- Success toast: “Password updated.”

# 6. Email Templates

## 6.1 Organisation Admin Invitation Email

**Trigger:** A new organisation is created by a Superadmin

**Recipient:** The email address entered in the Create Organisation form

**Subject:** You're invited to manage {OrganisationName}

### Body Outline

- Greeting addressing the organisation
- Brief explanation that a Superadmin created an organisation account on the platform and has invited them to be the Organisation Admin
- Primary CTA button: “Accept Invitation”
- Plain-text fallback of the full invitation URL
- Validity notice: “This invitation expires in 48 hours.”
- Footer with support contact and unsubscribe note where required

## 6.2 Invitation Resent Email

**Trigger:** Superadmin selects “Resend Invitation”

**Subject:** New invitation link for {OrganisationName}

The body is identical in structure to the original invitation email, with an additional note: “This replaces any previous invitation. The earlier link is no longer valid.”

## 6.3 Password Reset Email (Superadmin)

**Trigger:** User clicks “Forgot password?” on the Login page and submits a valid email

**Subject:** Reset your password

The body contains a time-limited reset link (1 hour validity), a plain-text fallback, and security messaging advising the user to ignore the email if they did not request a reset.

# 7. Technical Design

## 7.1 Technology Stack

| **Layer** | **Choice** |
| --- | --- |
| Language | Python 3.12+ |
| Backend framework | Django 6.0+ |
| API framework | Django REST Framework (latest compatible with Django 6) |
| Frontend | Django templates + Tailwind CSS, with React used for complex interactive components (dashboards, data tables, multi-step modals) |
| Database | PostgreSQL 16 |
| Cache, rate limiting, and distributed locks | Redis 7 |
| File storage | Google Cloud Storage |
| Authentication | Django built-in authentication with custom User model |
| Authorisation | Role-Based Access Control with custom DRF permission classes |
| Background jobs (Phase 1 and early Phase 2) | Django management commands triggered by Google Cloud Scheduler over authenticated HTTP |
| Background jobs (later phases) | Celery with Celery Beat, once workload justifies the migration |
| External integration (Phase 2 onwards) | Google Business Profile API via OAuth 2.0, one authorisation per store |
| Containerisation | Docker with docker-compose for local development |
| Hosting | Google Cloud (Cloud Run or GKE) |
| CI/CD | GitHub Actions |
| Error tracking | Sentry |
| Logs and uptime monitoring | Better Stack or Datadog |

## 7.2 High-Level Architecture

The platform is a monolithic Django application that serves both the server-rendered admin UI and the JSON API consumed by React components embedded in the page. A PostgreSQL database stores all persistent state. Redis backs the cache, rate limiting, session store, and distributed locks. Google Cloud Scheduler triggers scheduled jobs (such as Google review synchronisation in later phases) by making authenticated HTTP requests to internal endpoints that execute the relevant management commands.

## 7.3 Background Job Strategy

Phase 1 has minimal background workload — only outbound email, which is handled synchronously for simplicity or via Django 6's built-in Tasks framework if latency becomes an issue. From Phase 2 onwards, Google review synchronisation runs as a Django management command that is triggered on a schedule by Google Cloud Scheduler. The command delegates to a service function; no business logic lives in the command itself. When concurrency or retry requirements grow, the same service functions are wrapped as Celery tasks without rewriting any business logic.

## 7.4 Authentication and Authorisation

- A custom User model (apps.accounts.models.User) is defined before the first migration
- User.role is an enum field with values SUPERADMIN, ORG_ADMIN, and STAFF_ADMIN
- Users other than Superadmins are scoped to an organisation via a foreign key on the User model
- All Org Admin and Staff Admin querysets must be filtered by the caller's organisation. This tenant-scoping is enforced in a base permission class, not in individual views.
- The Django session backend is used for the server-rendered frontend. Token-based authentication (SimpleJWT) will be added only if a separate client is introduced.

## 7.5 Data Model Sketch (Phase 1)

### User

- id (PK)
- email (unique)
- full_name
- password_hash
- role: SUPERADMIN | ORG_ADMIN | STAFF_ADMIN
- organisation_id (nullable FK to Organisation)
- is_active
- created_at, updated_at, last_login_at

### Organisation

- id (PK)
- name
- type: RETAIL | RESTAURANT | PHARMACY | SUPERMARKET
- address (nullable)
- email (unique contact email for invitations)
- allocated_stores (integer)
- status: ACTIVE | DISABLED
- created_by_id (FK to User — the Superadmin who created it)
- created_at, updated_at

### OrganisationInvitation

- id (PK)
- organisation_id (FK)
- email (snapshot of the invited email)
- token_hash (one-way hash of the signed token)
- status: PENDING | ACCEPTED | EXPIRED | INVALIDATED
- sent_at, expires_at, accepted_at
- accepted_by_user_id (nullable FK)

### AuditLog

- id (PK)
- actor_id (FK to User, nullable for system events)
- action (enum, e.g. ORG_CREATED, ORG_DISABLED, INVITE_SENT, INVITE_ACCEPTED, INVITE_RESENT)
- target_type, target_id
- metadata (JSONB)
- created_at

## 7.6 Query Optimisation Requirements

- The Organisations list query must return the list with a fixed small number of SQL queries regardless of result size (strict no-N+1 policy)
- Store counts (used / allocated) must be computed via annotations, not per-row queries
- Every queryset in a list view must use select_related for forward foreign keys and prefetch_related for reverse or many-to-many relations
- A CI-level test using CaptureQueriesContext must assert an upper bound on the number of queries for every list endpoint

## 7.7 Redis Usage

- Caching of expensive aggregate reads (e.g., list pages with filters)
- DRF throttling for all endpoints
- Distributed locks for scheduled jobs that must not run concurrently for the same entity (used from Phase 2 for Google sync)
- Event-based cache invalidation on writes — cache keys for an organisation and for the organisations list are invalidated whenever an organisation is mutated

# 8. Non-Functional Requirements

## 8.1 Performance

- P95 API response time under 400ms for list endpoints with 1,000 organisations
- P95 page load under 2 seconds on broadband
- All list endpoints paginated with a default page size of 10

## 8.2 Availability

- Target uptime: 99.9% during business hours, 99.5% overall
- Health check endpoint /healthz/ and readiness endpoint /readyz/ verifying PostgreSQL and Redis connectivity

## 8.3 Security

- HTTPS enforced across all routes in production
- Secure cookies, HSTS with includeSubDomains and preload, CSRF protection, Content Security Policy
- Secrets stored in Google Cloud Secret Manager, never in environment files in production
- Password storage uses Django's default Argon2 hasher
- Sentry PII scrubbing is enabled; emails, names, and tokens are never sent to log aggregators

## 8.4 Compliance and Privacy

- Delete operations on an organisation perform a soft-delete (status change) in Phase 1; permanent deletion runs via a scheduled purge job after a grace period (future phase)
- Audit log retained for a minimum of 12 months

## 8.5 Observability

- Structured JSON logs in production with request_id, user_id, and organisation_id on every record
- Sentry captures unhandled exceptions
- Better Stack or Datadog aggregates logs and tracks uptime

# 9. Future Phases (Outline)

The following phases are outlined here for context only. Each will be specified in full in a future version of this document before implementation begins.

## 9.1 Phase 2 — Organisation Admin Module

- Organisation Admin dashboard and sidebar
- Store creation flow (limited by the allocated_stores count)
- Google Business Profile OAuth connection per store
- Staff Admin invitation flow
- Store listing, edit, enable/disable
- Organisation-level settings and profile

## 9.2 Phase 3 — Staff Admin Module

- Staff Admin dashboard scoped to assigned stores
- Review listing and response interface
- Store-level analytics

## 9.3 Phase 4 — Review Synchronisation

- Scheduled Google Business Profile review fetching
- Review storage, change tracking, and notifications
- Review analytics dashboards

## 9.4 Phase 5 — Billing and Plans

- Plan selection on organisation creation (multi-step form)
- Stripe integration
- Usage-based limits tied to the subscription plan

# 10. Phase 1 Acceptance Criteria

Phase 1 is considered complete when all of the following criteria are met.

- A Superadmin can log in and log out successfully.
- A Superadmin can create a new organisation with all required fields, and the system sends an invitation email to the organisation's email address.
- The organisation appears in the list with the correct name, type, email, store allocation, status, and creation date.
- Search, filter by status, filter by type, and pagination on the organisations list behave as specified.
- A Superadmin can edit an organisation (excluding email), and changes persist.
- A Superadmin can disable and re-enable an organisation with proper confirmation popups.
- A Superadmin can adjust the store allocation upward or downward (but never below the current in-use count), with proper confirmation.
- A Superadmin can delete an organisation only after typing its exact name into the confirmation input.
- A Superadmin can resend an invitation, which invalidates any previously generated token.
- The invitation recipient can click the email link, arrive at a pre-filled acceptance page, set their name and password, and successfully create the Organisation Admin account.
- Invitation tokens expire after 48 hours and show a clear error page if used after expiry or after acceptance.
- The Superadmin can update their profile name and change their password.
- All pages are fully responsive at desktop, tablet, and mobile breakpoints.
- All destructive actions show the correct confirmation popup and success toast as specified.
- The Organisations list renders within the query-count ceiling asserted in the CI test suite.
- All forms enforce the validation rules specified in Section 5.
- All emails render correctly in Gmail, Outlook, and Apple Mail.
