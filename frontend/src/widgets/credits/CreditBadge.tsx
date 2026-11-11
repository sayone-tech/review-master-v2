import { BADGE_BAND_CLASSES, creditBand } from "./creditBand";
import { creditsLabel } from "./format";
import { useShopCredits } from "./creditsStore";

export interface CreditBadgeProps {
  shopId: number;
  remaining: number | null | undefined;
  total: number | null | undefined;
  onOpen: () => void;
}

const BASE_CLS =
  "inline-flex items-center rounded-full px-2 py-1 text-[12px] font-semibold whitespace-nowrap focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink";

/**
 * Shops-list credits badge (CVIS-02). Text and colour come from the one shared
 * band helper; the store entry for the shop wins over the row values so the
 * badge agrees with an opened card.
 */
export function CreditBadge({ shopId, remaining, total, onOpen }: CreditBadgeProps) {
  const entry = useShopCredits(shopId);
  const rem = entry?.remaining ?? remaining;
  const tot = entry?.total ?? total;

  if (typeof rem !== "number" || typeof tot !== "number") {
    return <span className="text-muted">—</span>;
  }

  const band = creditBand(rem, tot);
  const label =
    band === "not_enabled"
      ? "Not enabled"
      : creditsLabel(rem);
  const hint =
    band === "not_enabled"
      ? "Not enabled — AI replies aren't enabled for this shop"
      : `${creditsLabel(rem)} remaining this month`;

  return (
    <button
      type="button"
      data-testid={`credits-badge-${shopId}`}
      className={`${BASE_CLS} ${BADGE_BAND_CLASSES[band]}`}
      title={hint}
      aria-label={hint}
      onClick={onOpen}
    >
      {label}
    </button>
  );
}
