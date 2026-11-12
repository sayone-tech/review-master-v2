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
/** Outcome of one request, tagged with its shop so a stale one is never shown. */
type Outcome = { shopId: number; data: ShopCredits } | { shopId: number; error: true };

export function CreditsCard({ shopId, shopName, focusOnMount, onBuyMore }: CreditsCardProps) {
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [attempt, setAttempt] = useState(0);
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
        setOutcome({ shopId, data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setOutcome({ shopId, error: true });
      });
    return () => controller.abort();
  }, [shopId, attempt]);

  // An outcome for another shop (fast switch) counts as still loading.
  const current = outcome && outcome.shopId === shopId ? outcome : null;
  const credits = current && "data" in current ? current.data : null;
  const failed = current !== null && "error" in current;

  const retry = () => {
    setOutcome(null);
    setAttempt((n) => n + 1);
  };

  useEffect(() => {
    if (!focusOnMount) return;
    const timer = setTimeout(() => headingRef.current?.focus(), 0);
    return () => clearTimeout(timer);
  }, [focusOnMount]);

  const band = credits ? creditBand(credits.remaining, credits.total) : null;
  const renews = credits ? formatUtcDate(credits.renews_on) : null;
  const loading = credits === null && !failed;

  const openBuyMore = () => {
    if (!credits) return;
    onBuyMore({
      name: shopName,
      remaining: credits.remaining,
      total: credits.total,
      isEnabled: credits.is_enabled,
      periodLabel: credits.period_label,
    });
  };

  return (
    <div
      data-testid="credits-card"
      aria-busy={loading ? "true" : undefined}
      className="bg-line-soft rounded-md p-4"
    >
      <div className="flex items-center gap-2">
        <Coins size={16} className="text-muted" aria-hidden="true" />
        <h3 ref={headingRef} tabIndex={-1} className="text-[14px] font-semibold text-ink">
          AI Reply Credits
        </h3>
        {credits?.period_label && (
          <span className="ml-auto text-[12px] text-muted">{credits.period_label}</span>
        )}
      </div>
      {loading && (
        <div className="mt-4 space-y-2" aria-hidden="true">
          <div className="animate-sk-pulse bg-line rounded-sm h-8 w-24" />
          <div className="animate-sk-pulse bg-line rounded-sm h-2 w-full" />
          <div className="animate-sk-pulse bg-line rounded-sm h-4 w-48" />
        </div>
      )}
      {failed && (
        <div
          role="alert"
          className="mt-4 bg-red-tint text-[#991B1B] rounded-md px-4 py-2 text-[12px]"
        >
          <p className="font-semibold">Couldn&apos;t load credits.</p>
          <p>Please try again.</p>
          <button
            type="button"
            onClick={retry}
            className="mt-2 h-8 px-4 text-[12px] font-normal bg-white text-ink border border-line rounded-md hover:bg-line-soft"
          >
            Retry Loading Credits
          </button>
        </div>
      )}
      {credits && band === "not_enabled" && (
        <>
          <p className="mt-4 text-[14px] text-muted">AI replies aren&apos;t enabled for this shop.</p>
          <div className="mt-4 flex justify-end">
            <button type="button" className={BUY_MORE_CLS} onClick={openBuyMore}>
              Buy More Credits
            </button>
          </div>
        </>
      )}
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
            <button type="button" className={BUY_MORE_CLS} onClick={openBuyMore}>
              Buy More Credits
            </button>
          </div>
        </>
      )}
    </div>
  );
}
