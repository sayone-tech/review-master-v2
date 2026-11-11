import { useEffect, useRef, useState } from "react";
import { Coins } from "lucide-react";
import { getShopCredits, type ShopCredits } from "./creditsApi";
import { BAR_BAND_CLASSES, creditBand, creditBarPercent } from "./creditBand";
import { creditsLabel, formatUtcDate } from "./format";
import { setShopCredits } from "./creditsStore";
import type { CreditRequestShop } from "./mailto";

export interface CreditsCardProps {
  shopId: number;
  shopName: string;
  focusOnMount?: boolean;
  onBuyMore: (shop: CreditRequestShop) => void;
}

const BUY_MORE_CLS =
  "h-8 px-4 text-[14px] font-normal bg-white text-ink border border-line rounded-md hover:bg-line-soft";

/**
 * AI Reply Credits card at the top of Shop Details (CVIS-01). Fetches the
 * balance fresh on every mount (D-11), writes it to the shop-keyed store so the
 * Shops badge agrees, and renders identically for Org Admin and Staff (D-10).
 */
export function CreditsCard({ shopId, shopName, focusOnMount, onBuyMore }: CreditsCardProps) {
  const [credits, setCredits] = useState<ShopCredits | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    getShopCredits(shopId, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setShopCredits(shopId, {
          remaining: data.remaining,
          total: data.total,
          isEnabled: data.is_enabled,
          periodLabel: data.period_label,
        });
        setCredits(data);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [shopId]);

  useEffect(() => {
    if (!focusOnMount) return;
    const timer = setTimeout(() => headingRef.current?.focus(), 0);
    return () => clearTimeout(timer);
  }, [focusOnMount]);

  const band = credits ? creditBand(credits.remaining, credits.total) : null;
  const renews = credits ? formatUtcDate(credits.renews_on) : null;

  return (
    <div data-testid="credits-card" className="bg-line-soft rounded-md p-4">
      <div className="flex items-center gap-2">
        <Coins size={16} className="text-muted" aria-hidden="true" />
        <h3 ref={headingRef} tabIndex={-1} className="text-[14px] font-semibold text-ink">
          AI Reply Credits
        </h3>
        {credits?.period_label && (
          <span className="ml-auto text-[12px] text-muted">{credits.period_label}</span>
        )}
      </div>
      {credits && band && band !== "not_enabled" && (
        <>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-[24px] font-semibold leading-[1.2] text-ink">
              {credits.remaining}
            </span>
            <span className="text-[24px] font-normal leading-[1.2] text-muted">
              / {credits.total}
            </span>
            <span className="text-[12px] text-muted">credits remaining</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-line">
            <div
              role="progressbar"
              aria-label="AI reply credits remaining"
              aria-valuemin={0}
              aria-valuemax={credits.total}
              aria-valuenow={credits.remaining}
              aria-valuetext={`${credits.remaining} of ${credits.total} credits remaining`}
              className={`h-2 rounded-full ${BAR_BAND_CLASSES[band]}`}
              style={{ width: `${creditBarPercent(credits.remaining, credits.total)}%` }}
            />
          </div>
          <p className="mt-2 text-[12px] text-muted">
            {creditsLabel(credits.consumed)} used · {creditsLabel(credits.remaining)} available
          </p>
          <p className="text-[12px] text-subtle">
            Monthly {credits.allocated} · Bonus {credits.bonus}
          </p>
          <div className="mt-4 flex items-center justify-between gap-2 flex-wrap">
            {renews ? (
              <span className="text-[12px] text-muted">Renews {renews} (UTC)</span>
            ) : (
              <span />
            )}
            <button
              type="button"
              className={BUY_MORE_CLS}
              onClick={() =>
                onBuyMore({
                  name: shopName,
                  remaining: credits.remaining,
                  total: credits.total,
                  isEnabled: credits.is_enabled,
                  periodLabel: credits.period_label,
                })
              }
            >
              Buy More Credits
            </button>
          </div>
        </>
      )}
    </div>
  );
}
