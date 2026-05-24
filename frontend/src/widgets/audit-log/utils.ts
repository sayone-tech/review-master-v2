// Phase 21-04 — Audit log utility helpers.
// formatRelativeDate is copied verbatim from
// frontend/src/widgets/review-management/ReviewTable.tsx (lines 37–49).
// Per UI-SPEC: copy rather than cross-import to keep widget boundaries clean.

export function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths === 1) return "1 month ago";
  if (diffMonths < 12) return `${diffMonths} months ago`;
  const diffYears = Math.floor(diffMonths / 12);
  return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
}

export const DEFAULT_DATE_WINDOW_DAYS = 30;

// WR-05 fix: format a Date as YYYY-MM-DD in the user's local timezone
// (NOT UTC). The previous implementation used `toISOString().split("T")[0]`,
// which is always UTC — leading to off-by-one date defaults for users in
// non-UTC timezones (e.g. IST after 18:30 local would default `date_to`
// to tomorrow). This util is the single source of truth; AuditLogFilters
// and useAuditLog both import it.
export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function defaultDateRange(): { date_from: string; date_to: string } {
  const today = new Date();
  const from = new Date(Date.now() - DEFAULT_DATE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  return { date_from: isoDate(from), date_to: isoDate(today) };
}
