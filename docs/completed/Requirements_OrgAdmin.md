**REQUIREMENTS DOCUMENT**

Multi-Tenant Review Management Platform

**Phase 2 — Organisation Admin Module**

Shops, Regions, and Team

Version 1.0 • April 2026

# 1. Document Overview

This document specifies Phase 2 of the multi-tenant Review Management Platform — the Organisation Admin module. It builds on the conventions, design system, and data model established in the Phase 1 (Superadmin) requirements document.

All global UI patterns, branding, design tokens, accessibility rules, and confirmation popup conventions defined in Phase 1 apply unchanged to Phase 2 and are not repeated here. Refer to the Phase 1 document for those baselines.

## 1.1 Phase 2 Scope

- Organisation Admin authentication and dashboard shell (sidebar, top bar, profile)
- Shops module — create, list, view, edit, activate / deactivate; Google Business Profile connection (OAuth) with manual fallback
- Regions module — create, list, edit, delete; auto-generated editable Region IDs
- Team module — invite team members, assign roles (Manager / Staff), scope access by Region and Store, enable / disable, remove
- Team invitation email and acceptance flow (reuses Phase 1 invitation infrastructure)
- Cross-module guidance and dependency enforcement (Region required for Shops, etc.)
- Updates to the data model and tech design to support Phase 2 entities

## 1.2 Out of Scope for Phase 2

- Org Admin Dashboard content (placeholder page only — content deferred)
- Staff Admin role dashboard and store-level views (Phase 3)
- Review fetching, storage, and analytics (Phase 4)
- Billing, subscriptions, and plan selection (Phase 5)
- Email change flow for users (deferred)

# 2. Roles and Terminology

Phase 2 introduces a Team module with two role labels visible to the Organisation Admin. These role labels map to the platform-level roles defined in Phase 1. The mapping must be respected across the codebase to avoid confusion.

| **UI Role Label (Phase 2)** | **Platform Role (data layer, Phase 1)** | **Meaning** |
| --- | --- | --- |
| Manager | ORG_ADMIN | Full access to all stores, regions, and team within the organisation. Can invite, edit, enable/disable, and remove other team members. |
| Staff | STAFF_ADMIN | Limited access to specific regions and/or stores assigned by a Manager. Can manage reviews and stores within scope (Phase 3+). |

## 2.1 Important — Terminology Disambiguation

The Team module's “Manager” label is org-scoped. It is NOT the same as the platform-level Superadmin (defined in Phase 1) which manages the entire platform across all organisations. Documentation, code, and support materials must use:

- “Superadmin” — only for the platform-level role (Phase 1)
- “Manager” — for the Team module's full-access role within an organisation (Phase 2)
- “Staff” — for the Team module's limited-access role within an organisation (Phase 2)
The original Organisation Admin (created via Superadmin's invitation in Phase 1) is automatically registered as the first Manager in their organisation's Team list.

# 3. Organisation Admin Dashboard Shell

## 3.1 Sidebar Menu

The Organisation Admin sees the following menu items in the left sidebar (using the global layout shell defined in Phase 1):

- Dashboard (LayoutDashboard icon) — default landing page (placeholder content for Phase 2)
- Shops (Store icon)
- Regions (Map icon)
- Team (Users icon)
- Profile (User icon)
- Logout (LogOut icon, bottom-pinned)

## 3.2 Default Landing Page

After login, the Organisation Admin lands on the Dashboard page. For Phase 2 this page displays a simple placeholder card with the heading “Welcome, {Name}” and the message “Your dashboard content will appear here in a future release. In the meantime, use the sidebar to manage your shops, regions, and team.”

If the Organisation Admin has zero Regions, a prominent yellow info banner appears at the top of the dashboard: “Get started by creating your first region. Regions are required to add shops.” with a “Create Region” CTA linking to /admin/org/regions.

## 3.3 Profile Page

The Profile page reuses the Phase 1 profile-page specification verbatim — same two-card layout (Profile Information, Change Password), same fields, same validation, same toasts. Route: /admin/org/profile.

# 4. Regions Module

Regions are lightweight grouping entities used to organise Shops. Every Shop must belong to exactly one Region. Regions are scoped to a single organisation.

## 4.1 Sidebar and Navigation

**Route:** /admin/org/regions

**Access:** Organisation Admin and any team Manager

**Page title:** Regions (N) — where N is the live count

## 4.2 Regions List Page

### Header Area

- Card title: “Regions”
- Card subtitle: “Manage regions for organizing your shops”
- Top-right primary action: “+ Add Region” button

### Table Columns

| **Column** | **Display** |
| --- | --- |
| Region Name | Plain text |
| Region ID | Pill badge (rounded border, monospace-style font) |
| Actions | Two direct icon buttons: Edit (pencil) and Delete (red trash). No three-dot menu. |

### Search, Filter, Pagination

Phase 2 does not include search, filter, or pagination on the Regions list. The list displays all regions for the organisation in creation order (oldest first). This may be revisited in a future phase if any organisation exceeds 20 regions.

### Empty State

- Centred Map icon
- Heading: “No regions yet”
- Body: “Regions are required to create shops. Add at least one region to get started.”
- CTA button: “Create your first region”

## 4.3 Create Region Modal

**Trigger:** “+ Add Region” button on the Regions list page

**Title:** Create New Region

**Subtitle:** Add a new region to organize your shops

### Fields

| **Field** | **Type** | **Required** | **Validation** | **Behaviour** |
| --- | --- | --- | --- | --- |
| Region Name | Text input | Yes | 2–60 characters | On change, auto-populates Region ID until the user manually edits the ID field. |
| Region ID | Text input | Yes | Uppercase letters and digits only (regex ^[A-Z0-9]+$), 2–10 characters, unique within the organisation | Auto-generated from Region Name (see §4.4). Editable at any time. Once manually edited, stops auto-updating. |

### Footer Buttons

- Cancel (secondary, left)
- Create Region (primary, right)

### Success Behaviour

- Modal closes
- Toast appears: “Region '{name}' created.”
- Regions list refreshes with the new row

## 4.4 Region ID Auto-Generation Rules

When the user types in the Region Name field of the Create modal, the Region ID field auto-populates in real time using the following algorithm:

- Take the uppercase first letter of each word in the Region Name (split by whitespace).
- Concatenate up to the first 4 such letters.
- Append a 3-digit sequence number, zero-padded, equal to (count of existing regions in this organisation + 1).
Examples (within an organisation that has no existing regions):

- “North District” → ND001
- “South District” → SD002
- “East District” → ED003
- “Bangalore” → B004
- “South West Central District” → SWCD005

### Manual Override Rules

- If the user manually edits the Region ID field, the auto-population stops for the remainder of the modal session.
- If the user clears the Region ID field after a manual edit, auto-population resumes.
- On the Edit Region modal, changes to the Region Name do NOT auto-update the Region ID (since it may be referenced elsewhere). The user can manually update the ID if needed.

### Uniqueness Validation

- Region ID is unique within the organisation. Submitting a duplicate ID shows an inline error on the field: “This Region ID is already in use.”
- Validation runs on submit (server-side authoritative) and may also run on blur (client-side check via debounced API call) for early feedback.

## 4.5 Edit Region Modal

**Trigger:** Pencil (Edit) icon in the actions column of the Regions list

**Title:** Edit Region

**Subtitle:** Update region information

### Fields

- Region Name — editable, same validation as Create
- Region ID — editable, same validation as Create. Note: changing the ID does NOT cascade to any displayed shop badges immediately; refresh the Shops list to see the update.

### Footer Buttons

- Cancel (secondary)
- Update Region (primary)

### Success Behaviour

- Toast: “Region updated.”
- Regions list refreshes

## 4.6 Delete Region

**Trigger:** Trash icon in the actions column

### Pre-Delete Check (Authoritative)

If the region has one or more Shops assigned to it, the delete action is BLOCKED. The confirmation popup is replaced with an information popup:

- Icon: Warning (amber)
- Title: “Cannot delete region”
- Message: “'{Region Name}' has {N} shop(s) assigned. Reassign or remove those shops before deleting this region.”
- Buttons: “Manage Shops” (secondary, links to /admin/org/shops with this region pre-filtered) and “Close” (primary)

### Standard Delete Confirmation (Region has no shops)

- Icon: Alert (red)
- Title: “Delete Region?”
- Message: “This will permanently delete '{Region Name}'. This cannot be undone.”
- Buttons: Cancel (secondary) / Delete (red)
- Success toast: “Region '{Region Name}' deleted.”

# 5. Shops Module

The Shops module is the core operational entity for the Organisation Admin. Each Shop represents one physical or logical store location, belongs to exactly one Region, and is connected to a Google Business Profile (preferred) or to the Google Places API via manual Place ID + API Key configuration (fallback).

## 5.1 Sidebar and Navigation

**Route:** /admin/org/shops

**Access:** Organisation Admin and any team Manager

**Page title:** Shops (X / Y) — where X is the count used and Y is the allocation set by Superadmin

## 5.2 Shops List Page

### Header Area

- Card title: “Shop Management”
- Card subtitle: “Manage your shop locations and their settings”
- Top-right primary action: “+ Add Shop” button

### Allocation Counter

The page header displays the live counter “Shops (X / Y)” where X is the current shop count for the organisation and Y is the allocation set by Superadmin in Phase 1. The counter updates immediately on shop create / activate / deactivate.

### Filter Bar

- Search input — placeholder “Search shops by name or address…”. Searches Shop Name + Street Address + City.
- Status filter dropdown: All / Active / Inactive
- Region filter dropdown: All / [list of regions in the organisation]

### Table Columns

| **Column** | **Display** |
| --- | --- |
| Shop Name | Bold text; clickable — opens the Shop Details modal |
| Location | Pin icon + Street Address (line 1), City + State + ZIP (line 2 in gray) |
| Region | Region badge (Region Name) |
| Contact | Phone icon + Phone Number |
| Google Place ID | Truncated Place ID (e.g., 'ChIJN1t_tDeu…') in monospace style |
| API Key | Key icon + masked API key (e.g., 'AIza…T7U8'). Only displayed for shops connected via manual fallback. Shows '—' for OAuth-connected shops. |
| Status | Badge — green “Active” or gray “Inactive” |
| Created | Date in M/D/YYYY format |
| Actions | Three-dot menu |

### Connection Status (in-row indicator)

An additional small status pill is shown next to the Status badge to indicate the Google connection health, distinct from the Active/Inactive lifecycle status:

- “Connected via Google” — green dot, OAuth connection healthy
- “Connected via API key” — blue dot, manual fallback configured
- “Connection error” — red dot, OAuth token expired or API key invalid; clicking opens the Shop Details modal with the Reconnect call-to-action
- “Quota exceeded” — amber dot, the configured API key has hit its Google quota

### Row Actions Menu

- View Details
- Edit Shop
- Activate / Deactivate (label toggles based on current status)
- Reconnect Google (visible only when Connection Status indicates an error)

### Pagination

- Bottom-right area
- Display: “Showing X–Y of Z”
- Rows-per-page selector: 10, 25, 50, 100 (default 10)
- Page navigation controls: first, previous, next, last

### Empty States

Two distinct empty states based on whether the organisation has any Regions:

### Empty State A — No regions exist

- Centred Store icon
- Heading: “Create a region first”
- Body: “Shops must belong to a region. Create at least one region before adding shops.”
- CTA button: “Go to Regions” (links to /admin/org/regions)

### Empty State B — Regions exist but no shops

- Centred Store icon
- Heading: “No shops yet”
- Body: “Add your first shop to start managing reviews and team access.”
- CTA button: “Add your first shop”

## 5.3 Allocated Stores Limit Enforcement

The Number of Stores allocated by Superadmin in Phase 1 is a hard ceiling enforced at the API layer.

- When the Org Admin clicks “+ Add Shop” and the allocation has been reached, the modal does NOT open.
- Instead, an error toast appears: “You've reached your shop limit ({Y} of {Y}). Contact your administrator to increase.”
- The “+ Add Shop” button is also visually disabled (gray) when at the limit, with a tooltip on hover: “Shop limit reached.”
- Deactivating a shop does NOT free up a slot. Only deletion (future phase) frees a slot. This is a deliberate decision to prevent accidental over-allocation churn.
- If Superadmin reduces the allocation below the current usage in Phase 1, the over-limit shops remain functional but the Org Admin cannot create new ones until usage falls below the new limit (this is consistent with the Phase 1 “cannot reduce below in-use count” guard).

## 5.4 Create Shop Modal

**Trigger:** “+ Add Shop” button on the Shops list page

**Title:** Create New Shop

**Subtitle:** Add a new shop location to your organization. All fields marked with * are required.

### Connection Method Selector (top of modal)

Radio group with two options. Default selection: “Connect with Google”.

- Connect with Google (recommended) — “Authorize via Google to sync all reviews”
- Enter manually — “Provide Google Place ID and API Key”

### Common Fields (always visible)

| **Field** | **Type** | **Required** | **Validation** | **Placeholder** |
| --- | --- | --- | --- | --- |
| Shop Name | Text input | Yes | 2–100 characters; unique within the organisation | Downtown Store |
| Phone Number | Text input | No | Optional; if provided, must match international format (E.164 recommended) | +1-555-0123 |
| Region | Dropdown | Yes | Must select one of the organisation's Regions. If no regions exist, dropdown is disabled and links to /admin/org/regions. | Select a region |
| Street Address | Text input | Yes | Max 200 characters | 123 Main Street |
| City | Text input | Yes | Max 100 characters | New York |
| State | Text input | No | Max 100 characters | NY |
| ZIP Code | Text input | No | Max 20 characters; format not enforced (international support) | 10001 |

### Method-Specific Fields — Connect with Google

- A single button replaces the manual fields: “Connect Google Business Profile” (secondary, with Google logo)
- After successful connection, displays a success row: green check + “Connected to {Listing Name} ({Listing Address})” and a “Change connection” link
- Helper text: “Authorizing connects this shop to your Google Business Profile listing. We'll fetch reviews and respond on your behalf.”

### Method-Specific Fields — Enter Manually

| **Field** | **Type** | **Required** | **Validation** | **Helper Text** |
| --- | --- | --- | --- | --- |
| Google Place ID | Text input | Yes | Must start with 'ChIJ' or one of Google's documented prefixes; 20–256 chars. Validated against Google Places API on submit. | You can find this ID using the Google Places API or Place ID Finder tool. (link) |
| Google Places API Key | Text input (masked, with show/hide toggle) | Yes | 39 characters typical; validated against Google Places API on submit. | This key should have Google Places API enabled. (link to setup guide) |

### Footer Buttons

- Cancel (secondary)
- Create Shop (primary)

### Submit Validation

- If method = Connect with Google: a successful OAuth connection must have completed (Connect button replaced with success row). Otherwise inline error: “Please connect to Google Business Profile to continue.”
- If method = Enter manually: server validates Place ID + API Key against the Google Places API once before saving. On failure: inline error: “Could not validate Place ID with the provided API key. Check both values and try again.”
- Both methods: API key (manual) or refresh token (OAuth) is encrypted at rest before persisting.

### Success Behaviour

- Modal closes
- Toast: “Shop '{Shop Name}' created.”
- Shops list refreshes; new row visible at the top
- Allocation counter increments by one

## 5.5 Google Business Profile OAuth Flow (Popup)

When the Org Admin clicks “Connect Google Business Profile” inside the Create Shop or Edit Shop modal, the OAuth flow runs in a popup window without disrupting the parent modal.

### Flow Steps

- Click triggers a popup of approximately 600×700px, centred on the parent screen, opened to the system OAuth start URL.
- Backend redirects the popup to Google's OAuth consent screen with the appropriate Business Profile scopes.
- User authenticates with their Google account.
- User grants the requested permissions (read access to Business Profile and reviews).
- Google redirects the popup to /oauth/google/callback/?code=… on our domain.
- Backend exchanges the code for a refresh token, fetches the list of business listings the user has access to.
- If multiple listings: callback page renders a listing-picker; user selects which listing represents this shop.
- If single listing: it is auto-selected and the picker step is skipped.
- Callback page calls window.opener.postMessage with { listingId, listingName, listingAddress } and auto-closes after 500ms.
- Parent modal listens for the message (origin verified), updates the connection state, and shows the success row.

### Edge Cases and Errors

- User closes popup before completing → parent modal shows error: “Connection cancelled. Please try again.”
- User denies consent → parent modal shows error: “Permission was not granted. Connection requires Business Profile access to fetch reviews.”
- Google API error during code exchange → parent modal shows error: “Could not complete connection. Please try again or contact support.”
- User has no Business Profile listings → callback page shows: “No business listings found in this Google account. Please ensure your business is verified on Google Business Profile and try again.”

### Security

- Refresh token is stored server-side only, encrypted at rest. It never reaches the browser.
- postMessage origin is verified against the application's allowed origin list before accepting any payload.
- OAuth state parameter is a cryptographically secure random value bound to the user session, preventing CSRF.
- Audit log entry on successful connection: { event: 'google.connected', shop_id, listing_id, user_id }

## 5.6 Shop Details Modal

**Trigger:** Clicking the Shop Name in the table, or “View Details” from the row actions menu

**Title:** The Shop Name

**Layout:** Read-only, two-column labelled grid

### Information Displayed

- Shop Name
- Region (badge)
- Status (badge — Active / Inactive)
- Connection Status (pill — Connected via Google / via API key / Connection error / Quota exceeded)
- Phone Number
- Street Address, City, State, ZIP
- Google Place ID (full, copyable)
- API Key (masked, with one-time Reveal action and Rotate Key action — manual fallback only)
- Connected Listing Name and Address (OAuth only)
- Created Date and Created By
- Last Updated timestamp

### Footer Buttons

- Reconnect Google (secondary, visible only on Connection error)
- Edit (secondary)
- Activate / Deactivate (secondary)
- Close (primary)

## 5.7 Edit Shop Modal

The Edit modal mirrors the Create modal layout, with current values pre-filled.

### Locked Fields

- Connection Method radio — locked. Once a shop is created via OAuth, it stays OAuth (use Reconnect Google to re-authorise). Once created via manual fallback, it stays manual (use Rotate Key to update the key).
- Google Place ID — locked. Changing the Place ID would change the shop's Google identity entirely; this is treated as creating a different shop.

### Editable Fields

- Shop Name
- Phone Number
- Region
- Street Address, City, State, ZIP
- Google Places API Key — manual fallback only, via Rotate Key action (see §5.9)

### Footer Buttons

- Cancel (secondary)
- Save Changes (primary)

### Success Behaviour

- Toast: “Shop updated.”
- Shops list refreshes

## 5.8 Activate / Deactivate Shop

**Trigger:** “Activate” or “Deactivate” option in the row actions menu, or button in the Shop Details modal

### Deactivate Confirmation Popup

- Icon: Warning (amber)
- Title: “Deactivate Shop?”
- Message: “'{Shop Name}' will stop syncing reviews and become inaccessible to assigned team members. You can reactivate it later. The allocated store slot remains used.”
- Buttons: Cancel / Deactivate (red)
- Success toast: “Shop '{Shop Name}' deactivated.”

### Activate Confirmation Popup

- Icon: Info (blue)
- Title: “Activate Shop?”
- Message: “'{Shop Name}' will resume review syncing and become accessible to assigned team members.”
- Buttons: Cancel / Activate (primary)
- Success toast: “Shop '{Shop Name}' activated.”

## 5.9 API Key Management (Manual Fallback Only)

### Reveal Key

- Trigger: “Reveal” button next to the masked key in the Shop Details modal
- Confirmation popup: “Reveal API key? The full key will be shown on screen. Make sure no one else can see it. The key will auto-hide after 30 seconds.”
- Buttons: Cancel / Reveal
- On confirm: full key shown for 30 seconds, then auto-masks again
- Audit log entry: { event: 'shop.api_key.revealed', shop_id, user_id }

### Rotate Key

- Trigger: “Rotate Key” button next to the masked key in the Shop Details modal
- Opens a small Rotate Key modal with one field: “New API Key” (text input, masked, show/hide toggle)
- Helper text: “Provide a new Google Places API key. The previous key will be replaced immediately.”
- On submit: server validates the new key against the Google Places API, then replaces (encrypted at rest)
- Success toast: “API key rotated for '{Shop Name}'.”
- Audit log entry: { event: 'shop.api_key.rotated', shop_id, user_id }

## 5.10 Reconnect Google (OAuth Only)

When an OAuth-connected shop's refresh token expires or is revoked, its Connection Status becomes “Connection error”. The Reconnect Google action restarts the OAuth popup flow described in §5.5. On success, the new refresh token replaces the old one and the connection status returns to healthy.

# 6. Team Module

The Team module lets the Organisation Admin invite, manage, and scope access for additional users within the organisation. Two roles are available: Manager (full access) and Staff (limited access).

## 6.1 Sidebar and Navigation

**Route:** /admin/org/team

**Access:** Organisation Admin and any team Manager

**Page title:** Team Management

## 6.2 Team List Page

### Header Area

- Card title with people icon: “Team Management”
- Card subtitle: “Manage team members and their access to stores”
- Top-right primary action: “+ Add Team Member” button (with person+plus icon)

### Filter Bar

- Search input — placeholder “Search by name or email…”. Searches Member Name + Email.
- Filter by Region dropdown — default “All Regions”
- Filter by Store dropdown — default “All Stores”. If a Region is selected, the Store dropdown narrows to stores within that region.

### Table Columns

| **Column** | **Display** |
| --- | --- |
| Member | Name (bold) on top; Email (with mail icon, gray) below |
| Role | Badge — purple shield “Manager” or gray person “Staff” |
| Access | One or more chips: “All Stores” crown badge for Manager; Region pin chips and/or Store building chips for Staff. If many, truncate with “+N more” and full list in tooltip / Details modal. |
| Status | Badge — green “Active” or amber “Pending” |
| Invited | Date in M/D/YYYY format |
| Enabled | Toggle switch (on/off, animated). Locked for the user's own row. |
| Actions | Two direct icon buttons: Edit (pencil) and Remove (red trash). Both disabled for the user's own row. |

### Stats Cards (bottom of page)

Three count cards displayed below the table:

- Total Members — black number
- Managers — purple number
- Active Members — green number

### Pagination

- Same pattern as Shops list: 10 per page default, with selector for 10/25/50/100

### Empty State

The Org Admin's own row always exists, so the table is never truly empty. However, when only the Org Admin exists (no other team members), display a banner above the table:

- Subtle info banner: “You're the only team member so far. Add others to share the workload.” with “+ Add Team Member” inline action.

## 6.3 Add Team Member Modal

**Trigger:** “+ Add Team Member” button

**Title:** Add Team Member

**Subtitle:** Invite a new team member and configure their access

### Always-Visible Fields

| **Field** | **Type** | **Required** | **Validation** | **Placeholder** |
| --- | --- | --- | --- | --- |
| Name | Text input | Yes | 2–100 characters | John Doe |
| Email | Email input | Yes | Valid email; unique across the platform | john@example.com |
| Role | Dropdown | Yes | One of: Manager, Staff | User (Limited access) — default |

### Role Dropdown Options

- Manager (Access to all stores) — purple shield icon
- Staff (Limited access) — gray person icon

### Conditional Fields — When Role = Manager

No additional fields appear. Manager has implicit access to all stores in the organisation.

- Helper text below the Role dropdown: “Managers have full access to all stores, regions, and team management.”

### Conditional Fields — When Role = Staff

Two multi-select sections appear. The user must select at least one Region OR at least one Store; selecting both is allowed. The “At least one selection required” rule is enforced on submit.

### Select Regions

- Heading: “Select Regions” (no asterisk — at least one of Region or Store is required)
- List of all Regions in the organisation as checkboxes
- Each item displays: Region Name + Region ID in parentheses (e.g., “North District (ND001)”)
- Helper text: “Staff will have access to all stores in selected regions.”

### Select Stores

- Heading: “Select Stores” (no asterisk — at least one of Region or Store is required)
- List of all active Shops in the organisation as checkboxes
- Each item displays: Shop Name + Region badge (so the Org Admin can see which region the shop belongs to)
- Helper text: “Staff will also have access to any individually selected stores.”
- Optional UI affordance: a “Filter by Region” dropdown above the Store list to narrow visible stores

### Validation Across Conditional Fields

- If Role = Staff and zero Regions and zero Stores selected: inline error below the conditional section: “Select at least one region or store to grant access.” The submit button is disabled until valid.
- If a Region is selected and a Store within that region is also selected: that's allowed. The Store selection is redundant but harmless.

### Footer Buttons

- Cancel (secondary)
- Send Invite (primary)

### Success Behaviour

- Modal closes
- Team list refreshes; new row appears with Status = Pending and Enabled = on
- Toast: “Invitation sent to {email}.”
- System sends a Team Invitation email (see §8.2) with a 48-hour token

## 6.4 Edit Team Member Modal

**Trigger:** Pencil (Edit) icon in the actions column. Disabled for the user's own row.

**Title:** Edit Team Member

**Subtitle:** Update team member information and access

### Editable Fields

- Name — editable
- Role — editable, with the same dropdown as Add modal. Changing role between Manager and Staff dynamically shows/hides the Region and Store selectors.
- Region selections (Staff role only) — editable
- Store selections (Staff role only) — editable

### Locked Fields

- Email — read-only. Email change requires a separate flow (deferred to a future phase).

### Footer Buttons

- Cancel (secondary)
- Save Changes (primary)

### Success Behaviour

- Toast: “Team member updated.”
- Team list refreshes; access chips reflect the new scope

## 6.5 Enable / Disable Team Member

The Enabled toggle in the table provides a quick on/off switch independent of the invitation lifecycle Status.

### Disable (Toggle ON → OFF)

- Confirmation popup required
- Icon: Warning (amber)
- Title: “Disable team member?”
- Message: “{Name} will be unable to log in until re-enabled. Their stored access scope is preserved.”
- Buttons: Cancel / Disable (red)
- Success toast: “{Name} disabled.”
- If the disabled user is currently logged in, all their active sessions are terminated immediately

### Enable (Toggle OFF → ON)

- No confirmation required (one-click)
- Success toast: “{Name} enabled.”

### Login Behaviour for Disabled Users

If a disabled user attempts to log in, the login form rejects with the error: “Your account has been disabled. Contact your administrator.”

## 6.6 Remove Team Member

**Trigger:** Trash (Remove) icon in the actions column. Disabled for the user's own row.

### Confirmation Popup

- Icon: Alert (red)
- Title: “Remove team member?”
- Message: “This will revoke access for {Name} ({email}). They will no longer be able to log in. This cannot be undone.”
- Buttons: Cancel / Remove (red)
- Success toast: “{Name} removed from team.”

### Effects

- User account is hard-deleted (or soft-deleted with a tombstone for audit purposes — implementation choice)
- All active sessions for the removed user are terminated
- Any pending invitations for the same email become invalid
- The same email can be re-invited later as a fresh team member

## 6.7 Self-Management Protection Rules

These rules apply to every Manager (including the original Org Admin) when viewing their own row in the Team list. Each protection has a UI tooltip explaining why the action is unavailable.

- Cannot remove self — Trash icon disabled. Tooltip: “You cannot remove yourself.”
- Cannot disable self — Enabled toggle locked in ON position. Tooltip: “You cannot disable yourself.”
- Cannot demote self to Staff — In Edit modal, the Role dropdown is disabled when editing self. Tooltip: “You cannot change your own role. Ask another Manager to change it.”
- Cannot change own email — Same as all users (locked field).
These protections are enforced both in the UI (button states, tooltips) AND at the API layer (server-side authoritative). Server returns 403 Forbidden with a clear error code if any of these is bypassed.

## 6.8 Multiple Managers

- An organisation can have multiple Managers. There is no upper limit.
- The original Org Admin (created via Superadmin's invitation in Phase 1) is automatically the first Manager and is registered in the Team table on first login.
- Any Manager can invite, edit, enable/disable, and remove other team members (subject to the self-protection rules in §6.7).
- Removing the last remaining Manager from an organisation is BLOCKED at the API layer. Error: “Cannot remove the last Manager. Promote another team member to Manager first.”

## 6.9 Team Invitation Acceptance Flow

The Team invitation acceptance flow reuses the Phase 1 Org Admin invitation infrastructure (route, page, security model). The differences are noted below.

### Reused from Phase 1

- Route: /invite/accept/<token>/
- Layout: centred card, no sidebar
- Token security: cryptographically secure random string, signed with TimestampSigner, single-use, 48-hour expiry
- Resending an invitation invalidates any previously generated token for the same invitation
- Audit log entries for invite sent / accepted / expired / resent
- Error pages for invalid/expired token and already-used token

### Differences from Phase 1

- Page heading: “Welcome to {Organisation Name}” (same as Phase 1) but subtitle: “Create your team account to get started.”
- Email field is pre-filled and locked (same as Phase 1)
- Name field is pre-filled with the name the Org Admin entered when sending the invite, but is editable by the invitee
- Password and Confirm Password fields use the same Django default validators and strength indicator as Phase 1
- On success: account created with role Manager or Staff as configured in the invitation. User is auto-logged in and redirected to their dashboard:
- Manager → Org Admin Dashboard (/admin/org/dashboard)
- Staff → Staff Dashboard (Phase 3 — for Phase 2, redirect to a placeholder “Welcome” page)

## 6.10 Resend Invitation

For team members with Status = Pending, the Org Admin can resend the invitation. The action is available from the row actions area (an additional icon shown only for Pending rows, or an option exposed via a contextual menu).

### Confirmation Popup

- Icon: Mail (blue)
- Title: “Resend invitation?”
- Message: “A new invitation link will be sent to {email}. The previous link will be invalidated.”
- Buttons: Cancel / Resend (primary)
- Success toast: “Invitation resent to {email}.”

# 7. Cross-Module Behaviours

## 7.1 Region Required for Shops

- A shop cannot exist without a Region. Region is required at create time and cannot be cleared at edit time (only changed).
- Empty state on Shops page when no Regions exist directs the user to create a Region first (see §5.2 Empty State A).
- Region dropdown in Create / Edit Shop is disabled when no Regions exist, with a link to /admin/org/regions.

## 7.2 Region Deletion Blocked by Shops

- A Region with assigned Shops cannot be deleted (see §4.6).
- To delete a Region, the Org Admin must first reassign or deactivate (and later remove) all shops in that region.

## 7.3 Shop Activation Affects Team Access

- When a shop is deactivated, Staff members assigned to it (directly or via region) lose access to that shop's data until reactivation.
- Inactive shops are excluded from the “Select Stores” list in the Add Team Member and Edit Team Member modals.

## 7.4 Region Deletion / Edit Affects Team Access

- When a Region is renamed or its ID changes, all team access scopes auto-update by reference (no data fix required).
- If a Region were ever deleted (only possible when it has no shops), any Staff scoped to it via region would have that scope entry removed. This is rare since regions with shops cannot be deleted, but the API and UI must handle it gracefully.

## 7.5 Allocation Counter Source of Truth

- The “X / Y” counter on the Shops page is computed server-side from the canonical organisation allocation.
- It is updated transactionally on shop create / activate / deactivate to avoid race conditions across concurrent admin sessions.

# 8. Email Templates

## 8.1 Team Invitation Email

**Trigger:** Org Admin or Manager sends a new team invitation

**Recipient:** Invited email address

**Subject:** You're invited to join {OrganisationName}

### Body Outline

- Greeting addressing the invitee by name (collected at invitation time)
- Brief explanation: “{Inviter Name} has invited you to join {OrganisationName} as a {Role Label}.”
- If Role = Staff, optional summary: “You'll have access to: {comma-separated list of Region names and/or Store names}.”
- Primary CTA button: “Accept Invitation”
- Plain-text fallback of the full invitation URL
- Validity notice: “This invitation expires in 48 hours.”
- Footer with support contact and unsubscribe note where required

## 8.2 Team Invitation Resent Email

**Trigger:** Org Admin or Manager selects “Resend Invitation” for a Pending team member

**Subject:** New invitation link for {OrganisationName}

Body identical in structure to the original Team Invitation, with an added line: “This replaces any previous invitation. The earlier link is no longer valid.”

# 9. Technical Design Updates

The Phase 1 tech design (stack, services pattern, query optimisation, Redis usage, Amazon SES email, etc.) applies unchanged. This section adds Phase 2 entities, updates to existing entities, and Phase-2-specific integration notes.

## 9.1 Data Model Additions

### Region

- id (PK, UUID)
- organisation_id (FK to Organisation, indexed)
- name (string, 60 chars)
- region_code (string, 10 chars, uppercase + digits, unique within organisation)
- created_by_id (FK to User)
- created_at, updated_at
- Unique constraint: (organisation_id, region_code)
- Unique constraint: (organisation_id, name)

### Shop

- id (PK, UUID)
- organisation_id (FK to Organisation, indexed)
- region_id (FK to Region, indexed)
- name (string, 100 chars)
- phone_number (string, nullable)
- street_address, city, state, zip_code (strings; state and zip nullable)
- google_place_id (string, immutable after creation)
- connection_method: OAUTH | MANUAL
- connection_status: HEALTHY | EXPIRED | INVALID_KEY | QUOTA_EXCEEDED | ERROR
- google_listing_id (string, OAuth only)
- google_listing_name, google_listing_address (strings, OAuth only)
- encrypted_api_key (binary, manual fallback only)
- encrypted_oauth_refresh_token (binary, OAuth only)
- status: ACTIVE | INACTIVE
- created_by_id (FK to User)
- created_at, updated_at
- Unique constraint: (organisation_id, name)
- Unique constraint: (organisation_id, google_place_id)

### StaffAccessScope

Junction model representing a Staff user's access to a Region or to a specific Shop. One row per scope grant.

- id (PK)
- user_id (FK to User, indexed)
- scope_type: REGION | SHOP
- region_id (FK to Region, nullable, indexed)
- shop_id (FK to Shop, nullable, indexed)
- created_at
- Constraint: exactly one of region_id or shop_id is non-null
- Unique constraint: (user_id, scope_type, region_id, shop_id)

### Updates to Existing Entities

- User: add invited_by_id (nullable FK to User), invited_at, accepted_at
- OrganisationInvitation: rename to UserInvitation; add purpose enum (ORG_ADMIN | TEAM_MANAGER | TEAM_STAFF), reused for Phase 2 team invitations
- AuditLog: add new actions — region.created, region.updated, region.deleted, shop.created, shop.updated, shop.activated, shop.deactivated, shop.api_key.revealed, shop.api_key.rotated, google.connected, google.disconnected, team.invited, team.role_changed, team.scope_updated, team.enabled, team.disabled, team.removed

## 9.2 Permissions and Tenant Scoping

All Phase 2 endpoints must enforce tenant scoping at the permission layer (per CLAUDE.md §9). The base IsOrgScoped permission filters every queryset by request.user.organisation_id.

### Endpoint Permission Matrix

| **Endpoint Group** | **Required Role** | **Additional Scope** |
| --- | --- | --- |
| /api/v1/regions/* | ORG_ADMIN or any Manager (Team) | Filtered by organisation |
| /api/v1/shops/* | ORG_ADMIN or Manager | Filtered by organisation; reads only return shops in user's scope for Staff (Phase 3) |
| /api/v1/team/* | ORG_ADMIN or Manager | Filtered by organisation |
| /api/v1/team/{id}/ enable/disable/remove | ORG_ADMIN or Manager | Subject to self-protection rules (§6.7) and last-Manager rule (§6.8) |
| /oauth/google/* and /webhooks/ses/* | Public or signed | Origin/signature verified |

## 9.3 Google Business Profile OAuth — Implementation Notes

- OAuth client lives in apps/integrations/google/ (per CLAUDE.md §11)
- Required scopes: business.manage (or equivalent read-write per Google's current spec); locations:read for listing enumeration
- Refresh tokens encrypted at rest using django-cryptography or Fernet with a key from GCP Secret Manager
- OAuth state parameter is a signed token bound to the user's session and the target shop draft (for new shops) or shop_id (for reconnect)
- Callback handler runs inside @transaction.atomic to ensure (token store + audit log) succeed or fail together
- postMessage payload from callback to opener includes only listing_id, listing_name, listing_address — never tokens
- Token refresh job is scheduled hourly via management command + Cloud Scheduler (Phase 1 pattern); runs apps/reviews/management/commands/refresh_google_tokens.py

## 9.4 Google Places API — Manual Fallback Notes

- API key encryption follows the same pattern as OAuth refresh tokens
- Place ID + API Key validation on submit hits the Google Places Details endpoint with fields=place_id once; success means both values are valid
- Quota tracking per shop is maintained in Redis with a 24-hour rolling window; near-quota warnings update the shop's connection_status to QUOTA_EXCEEDED preemptively
- Rate limiting at the application layer (DRF throttle scope google_sync = 60/minute per CLAUDE.md §7.5)

## 9.5 Region ID Generation — Implementation Notes

- Generation logic lives in apps/organisations/services/regions.py as generate_region_code(organisation_id, name)
- Sequence number is computed via SELECT COUNT(*) FROM regions WHERE organisation_id = ? + 1 inside the same transaction as the insert (with select_for_update on the organisation row to prevent race conditions)
- On collision (extremely rare race), retry up to 3 times with the next sequence number
- Client-side preview uses the same algorithm but is non-authoritative; server-side generation always wins on actual submit

## 9.6 Query Optimisation Requirements (Phase 2 Specifics)

- Shops list query must join Region (select_related) and prefetch any related team scopes for display
- Team list query must select_related User → invited_by, prefetch_related staff_access_scopes → region and staff_access_scopes → shop, and annotate counts for the stats cards in a single aggregate query
- Regions list query must annotate shop_count for the empty-state and pre-delete-check logic
- All Phase 2 list endpoints must have CaptureQueriesContext tests asserting fixed query-count ceilings regardless of result size (per CLAUDE.md §6.9)

# 10. Phase 2 Acceptance Criteria

Phase 2 is considered complete when all of the following criteria are met.

## 10.1 Shell and Navigation

- On first login, the Org Admin lands on the Dashboard placeholder page with the welcome message and (if applicable) the “create your first region” banner.
- The sidebar shows Dashboard, Shops, Regions, Team, Profile, Logout in the specified order with role-correct active state.

## 10.2 Regions

- Org Admin can create a Region; the Region ID auto-generates from the name and can be manually overridden.
- Region IDs are unique within the organisation; duplicates are blocked with a clear inline error.
- Org Admin can edit a Region's name and ID.
- Org Admin can delete a Region only when it has no shops; the block popup explains the reason and offers a “Manage Shops” link.
- The Regions list, edit modal, delete popup, and toasts behave per spec.

## 10.3 Shops

- Org Admin sees the “X / Y” allocation counter at the top of the Shops page.
- “+ Add Shop” is disabled and shows a tooltip when at the allocation limit; clicking it shows the limit error toast.
- Org Admin can create a Shop using the OAuth flow — popup opens, completes, and parent modal shows connected listing details.
- Org Admin can create a Shop using the manual fallback — Place ID + API Key validated against Google Places API on submit.
- Shop list shows correct columns, search/filter/pagination behave per spec, and the connection-status pill reflects real connection health.
- Edit Shop locks the connection method and Google Place ID; all other fields are editable.
- Activate / Deactivate flows show the correct confirmation popups and toasts; deactivation does NOT free an allocation slot.
- API Key Reveal action shows the key for 30 seconds and writes an audit log entry; Rotate Key validates the new key and replaces the old one atomically.
- Reconnect Google action restarts the OAuth popup flow and updates the stored refresh token on success.

## 10.4 Team

- The Org Admin appears in their own Team list as a Manager with “All Stores” access.
- Self-protection rules are enforced (cannot remove, disable, or demote self).
- Last-Manager rule is enforced (cannot remove the last Manager).
- Org Admin can invite a Manager (no scope selection) and a Staff member (with at least one Region or Store).
- Invited team members receive the email, can accept within 48 hours, and land on their role-appropriate dashboard.
- Resend Invitation invalidates the previous token and sends a new email.
- Edit Team Member updates name, role, and scope; switching role between Manager and Staff dynamically shows / hides scope selectors.
- Enable / Disable toggle behaves per spec, including immediate session termination on disable.
- Remove Team Member shows the confirmation popup and revokes access permanently.
- Stats cards (Total Members, Managers, Active Members) reflect accurate counts.

## 10.5 Cross-Cutting

- All list endpoints render within the query-count ceilings asserted in CI tests.
- All forms enforce the validation rules specified in this document.
- All emails render correctly in Gmail, Outlook, and Apple Mail.
- All pages are fully responsive at desktop, tablet, and mobile breakpoints (per Phase 1 design contract).
- All destructive actions show the correct confirmation popup and success / error toast.
- All audit log events listed in §9.1 are written and queryable.
- Tenant scoping is enforced at the API layer for every Phase 2 endpoint; cross-organisation access is impossible.
