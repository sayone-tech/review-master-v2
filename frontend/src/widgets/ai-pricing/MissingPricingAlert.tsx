import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { ApiError, fetchMissing, refreshMissing } from "./api";
import type { MissingModel } from "./types";

interface Props {
  variant: "pricing" | "cost-explorer";
  onAddFor?: (model: string) => void;
  /** Change this value to refetch (e.g. after a price is added or deleted). */
  refreshKey?: number;
  /** When true (pricing variant), note that the weekly LiteLLM sync may fill the gap. */
  syncEnabled?: boolean;
}

/** Amber alert listing models logged without pricing as chips. Renders nothing when none. */
export function MissingPricingAlert({ variant, onAddFor, refreshKey = 0, syncEnabled = false }: Props) {
  const [models, setModels] = useState<MissingModel[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const req = useRef(0);

  useEffect(() => {
    const mine = ++req.current;
    fetchMissing()
      .then((r) => {
        if (mine === req.current) setModels(r.models);
      })
      .catch(() => {
        // Advisory banner: a failed check must not break the page; it just stays hidden.
        if (mine === req.current) setModels([]);
      });
  }, [refreshKey]);

  const refresh = useCallback(() => {
    const mine = ++req.current;
    setRefreshing(true);
    setNotice(null);
    refreshMissing()
      .then((r) => {
        if (mine === req.current) setModels(r.models);
      })
      .catch((e: unknown) => {
        if (mine !== req.current) return;
        setNotice(
          e instanceof ApiError && e.status === 429
            ? "Please wait a minute before checking again."
            : "Could not check for missing prices.",
        );
      })
      .finally(() => {
        if (mine === req.current) setRefreshing(false);
      });
  }, []);

  if (models.length === 0) return null;

  const n = models.length;
  const pricing = variant === "pricing";
  return (
    <div
      className="rounded-card bg-amber-tint px-4 py-3 text-[13.5px] text-ink"
      data-testid="missing-pricing-alert"
    >
      <div className="flex gap-2.5">
        <AlertTriangle size={16} aria-hidden="true" className="mt-0.5 shrink-0 text-amber" />
        <div className="min-w-0 flex-1 space-y-2">
          <p>
            <strong className="font-semibold">
              {n} {n === 1 ? "model is" : "models are"} logged without pricing.
            </strong>{" "}
            These calls show $0 in cost totals until pricing is added.
            {models.some((x) => x.configured) && " Enrichment fails until the configured model has a price."}
          </p>
          <ul className="flex flex-wrap gap-1.5" aria-label="Models without pricing">
            {models.map((m) => (
              <li
                key={m.model}
                className={`inline-flex items-center gap-1.5 rounded-full border border-line bg-white py-0.5 text-[12.5px] ${pricing ? "pl-2.5 pr-1" : "px-2.5"}`}
              >
                <span className="font-medium">{m.model}</span>
                {m.configured && <span className="text-muted">(configured model)</span>}
                {pricing && (
                  <button
                    type="button"
                    onClick={() => onAddFor?.(m.model)}
                    aria-label={`Add price for ${m.model}`}
                    className="rounded-full px-2 py-0.5 font-medium text-ink underline-offset-2 hover:bg-line-soft hover:underline"
                  >
                    Add price
                  </button>
                )}
              </li>
            ))}
          </ul>
          {pricing && syncEnabled && (
            <p className="text-muted">
              The next weekly sync (Mon 09:00 UTC) fetches LiteLLM pricing for the models it covers.
            </p>
          )}
          {pricing ? (
            <button
              type="button"
              onClick={refresh}
              disabled={refreshing}
              className="rounded-sm text-[13px] font-medium text-ink underline underline-offset-2 hover:no-underline disabled:opacity-50"
            >
              Check again
            </button>
          ) : (
            <a
              href="/admin/ai-pricing/"
              className="inline-block rounded-sm text-[13px] font-medium underline underline-offset-2 hover:no-underline"
            >
              Go to AI Pricing
            </a>
          )}
          {notice && (
            <p role="status" className="text-[12.5px] text-muted">
              {notice}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
