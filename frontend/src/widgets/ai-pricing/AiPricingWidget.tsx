import { useCallback, useEffect, useState } from "react";
import { fetchHistory, fetchPriceSummary } from "./api";
import { HistoryRows } from "./HistoryRows";
import { AddPriceButton, PricesTable } from "./PricesTable";
import type { Paginated, PriceRow, PriceSummary } from "./types";

export function AiPricingWidget() {
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState<Paginated<PriceSummary> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [history, setHistory] = useState<PriceRow[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const loadSummary = useCallback(() => {
    setError(null);
    return fetchPriceSummary(page)
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [page]);

  const loadHistory = useCallback((model: string) => {
    setHistoryError(null);
    return fetchHistory(model)
      .then((r) => setHistory(r.results))
      .catch((e: unknown) =>
        setHistoryError(e instanceof Error ? e.message : "Failed to load history"),
      );
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  const toggleHistory = (model: string) => {
    if (expanded === model) {
      setExpanded(null);
      return;
    }
    setExpanded(model);
    setHistory(null);
    void loadHistory(model);
  };

  const afterDelete = () => {
    void loadSummary();
    if (expanded) void loadHistory(expanded);
  };

  const totalPages = summary ? Math.max(1, Math.ceil(summary.count / 25)) : 1;

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold text-ink">AI Pricing</h1>
          <p className="text-[13.5px] text-muted">
            Current and historical token rates for OpenAI models
          </p>
        </div>
        <AddPriceButton
          label="Add New Price"
          className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </header>

      {error && (
        <div role="alert" className="text-[13px] text-red">
          {error}{" "}
          <button type="button" className="underline" onClick={() => void loadSummary()}>
            Retry
          </button>
        </div>
      )}

      {summary && (
        <PricesTable
          rows={summary.results}
          expandedModel={expanded}
          onViewHistory={toggleHistory}
          renderExpanded={() => {
            if (historyError)
              return (
                <div role="alert" className="text-[13px] text-red">
                  {historyError}
                </div>
              );
            if (!history) return <p className="text-[13px] text-muted">Loading history…</p>;
            return <HistoryRows rows={history} onDeleted={afterDelete} />;
          }}
        />
      )}

      {summary && summary.count > 25 && (
        <nav aria-label="Pagination" className="flex items-center gap-2 text-[12px] text-muted">
          <button
            type="button"
            className="px-2 py-1 rounded-sm border border-line bg-white disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="px-2 py-1 rounded-sm border border-line bg-white disabled:opacity-40"
            disabled={!summary.next}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </nav>
      )}
    </div>
  );
}
