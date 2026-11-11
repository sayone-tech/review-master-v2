/**
 * Pure helpers for the "Monthly credits per shop" field (Create + Edit
 * Organisation) and the credits UI that follows (Manage Credits, View Org).
 *
 * The live hint mirrors the backend timing rule (CRED-06, D-18):
 *   - a change is immediate only when no shop has a positive allocation this
 *     month (saved value 0 AND this month's value 0);
 *   - otherwise the change takes effect on the 1st of the next UTC month.
 *
 * The "keep" number in the deferred copy is `current_month_credit_allocation`
 * (D-21), NOT the saved value: after 100 -> 0 -> 50 the saved value is 0 but
 * shops still hold 100 this month.
 *
 * Dates are built from UTC getters and hard-coded month names. Never use
 * locale date formatting: en-GB renders September as "Sept" and the server's
 * credit period is UTC.
 */

export const MONTH_NAMES_SHORT: readonly string[] = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export const MONTH_NAMES_LONG: readonly string[] = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const CREDIT_MIN = 0;
export const CREDIT_MAX = 10000;

export type CreditHintKind =
  | "off"
  | "immediate"
  | "deferred"
  | "deferred-off"
  | "hidden";

export interface CreditHint {
  kind: CreditHintKind;
  text: string;
}

/** Whole number 0..10,000, else null. Trims surrounding whitespace. */
export function parseCreditInput(raw: string): number | null {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const n = Number(trimmed);
  return n >= CREDIT_MIN && n <= CREDIT_MAX ? n : null;
}

/** First day of the next UTC month, e.g. "1 Dec 2026". December rolls to January. */
export function formatNextMonthStart(nowUtc: Date): string {
  const month = nowUtc.getUTCMonth();
  const year = nowUtc.getUTCFullYear();
  const nextMonth = (month + 1) % 12;
  const nextYear = month === 11 ? year + 1 : year;
  return `1 ${MONTH_NAMES_SHORT[nextMonth]} ${nextYear}`;
}

/** month is 1..12; e.g. (2026, 11) -> "November 2026". */
export function formatMonthYear(year: number, month: number): string {
  return `${MONTH_NAMES_LONG[month - 1]} ${year}`;
}

/** Thousands separator: 1000 -> "1,000". */
export function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

const OFF_COPY = "0 means AI replies are off for this organisation.";
const IMMEDIATE_COPY = "Takes effect immediately for this month.";

export function computeCreditHint(args: {
  mode: "create" | "edit";
  saved: number;
  thisMonth: number;
  typed: string;
  nowUtc: Date;
}): CreditHint {
  const { mode, saved, thisMonth, typed, nowUtc } = args;
  const m = parseCreditInput(typed);
  if (m === null) return { kind: "hidden", text: "" };

  if (mode === "create") {
    return m === 0
      ? { kind: "off", text: OFF_COPY }
      : { kind: "immediate", text: IMMEDIATE_COPY };
  }

  if (m === saved) {
    return m === 0 ? { kind: "off", text: OFF_COPY } : { kind: "hidden", text: "" };
  }
  if (saved === 0 && thisMonth === 0) {
    return { kind: "immediate", text: IMMEDIATE_COPY };
  }
  const date = formatNextMonthStart(nowUtc);
  if (m > 0) {
    return {
      kind: "deferred",
      text: `Takes effect on ${date}. Shops keep ${thisMonth} this month.`,
    };
  }
  return {
    kind: "deferred-off",
    text: `Takes effect on ${date}. Shops keep ${thisMonth} this month, then AI replies turn off.`,
  };
}
