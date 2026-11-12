import { useCallback, useEffect, useRef, useState } from "react";
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

/** Amber alert listing models logged without pricing. Renders nothing when none. */
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
            ? "Please wait a minute before refreshing again."
            : "Could not refresh the missing-pricing check.",
        );
      })
      .finally(() => {
        if (mine === req.current) setRefreshing(false);
      });
  }, []);

  if (models.length === 0) return null;

  const n = models.length;
  return (
    <div
      className="bg-amber-50 border border-amber-300 rounded-card p-4 text-[13.5px] text-ink space-y-2"
      data-testid="missing-pricing-alert"
    >
      <p>
        <span aria-hidden="true">⚠ </span>
        <strong>
          {n} {n === 1 ? "model is" : "models are"} logged without pricing.
        </strong>{" "}
        These calls show $0 in cost totals until pricing is added.
        {models.some((x) => x.configured) && " Enrichment fails until the configured model has a price."}
      </p>
      <p>
        Missing:{" "}
        {models.map((m, i) => (
          <span key={m.model}>
            {i > 0 && ", "}
            <code className="font-mono text-[12.5px]">{m.model}</code>
            {m.configured && <span className="text-muted"> (configured model)</span>}
          </span>
        ))}
      </p>
      {variant === "pricing" && syncEnabled && (
        <p>
          Next weekly sync (Mon 09:00 UTC) will fetch pricing from LiteLLM automatically for models it
          covers.
        </p>
      )}
      {variant === "cost-explorer" ? (
        <a href="/admin/ai-pricing/" className="inline-block font-medium underline underline-offset-2">
          Go to AI Pricing →
        </a>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {models.map((m) => (
            <button
              key={m.model}
              type="button"
              onClick={() => onAddFor?.(m.model)}
              className="px-3 py-1.5 bg-yellow text-black border border-yellow-hover rounded-md text-[13px] font-medium hover:bg-yellow-hover"
            >
              Add pricing for {m.model} →
            </button>
          ))}
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="px-3 py-1.5 bg-white border border-line rounded-md text-[13px] hover:bg-line-soft disabled:opacity-50"
          >
            Refresh missing-pricing check
          </button>
        </div>
      )}
      {notice && (
        <p role="status" className="text-[12.5px] text-muted">
          {notice}
        </p>
      )}
    </div>
  );
}
