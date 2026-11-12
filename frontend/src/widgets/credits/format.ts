import { MONTH_NAMES_SHORT, formatCount } from "../org-management/creditHint";

/** "1 credit" | "{n} credits" with en-US thousands separators (D-02). */
export function creditsLabel(n: number): string {
  return n === 1 ? "1 credit" : `${formatCount(n)} credits`;
}

const ISO_DATE = /^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

/**
 * "YYYY-MM-DD" -> "1 Dec 2026" (D-04). Pure string handling with the shared
 * hard-coded month names: no Date construction and no locale formatting, so the
 * result never depends on the process time zone and September stays "Sep"
 * (en-GB renders "Sept" — deliberate deviation from the UI-SPEC note).
 */
export function formatUtcDate(isoDate: string): string | null {
  const match = ISO_DATE.exec(isoDate);
  if (!match) return null;
  const [, year, month, day] = match;
  return `${Number(day)} ${MONTH_NAMES_SHORT[Number(month) - 1]} ${year}`;
}
