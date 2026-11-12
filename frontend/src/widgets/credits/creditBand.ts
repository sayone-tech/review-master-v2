/**
 * The single D-03 band helper shared by the credits card, the Shops badge and
 * the composer. Integer maths only: no float division decides a band.
 *
 *   total 0            -> not_enabled (never divides)
 *   remaining <= 0     -> empty
 *   remaining > 25%    -> green
 *   5% <= remaining <= 25% -> amber (25% and 5% exactly are amber)
 *   remaining < 5%     -> red
 */
export type CreditBand = "not_enabled" | "empty" | "green" | "amber" | "red";

export function creditBand(remaining: number, total: number): CreditBand {
  if (total <= 0) return "not_enabled";
  if (remaining <= 0) return "empty";
  if (remaining * 100 > total * 25) return "green";
  if (remaining * 100 >= total * 5) return "amber";
  return "red";
}

/** Integer 0..100 fill for the progress bar; 0 when total is 0 (no divide-by-zero). */
export function creditBarPercent(remaining: number, total: number): number {
  if (total <= 0) return 0;
  const clamped = Math.min(Math.max(remaining, 0), total);
  return Math.round((clamped * 100) / total);
}

export const BADGE_BAND_CLASSES: Record<CreditBand, string> = {
  green: "bg-green-tint text-[#166534]",
  amber: "bg-amber-tint text-[#92400E]",
  red: "bg-red-tint text-[#991B1B]",
  empty: "bg-muted text-white",
  not_enabled: "bg-line-soft text-muted",
};

export const BAR_BAND_CLASSES: Record<Exclude<CreditBand, "not_enabled">, string> = {
  green: "bg-green",
  amber: "bg-amber",
  red: "bg-red",
  empty: "bg-muted",
};
