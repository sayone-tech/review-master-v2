import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHistory, fetchPriceSummary } from "./api";
import { AddPriceModal } from "./AddPriceModal";
import { HistoryRows } from "./HistoryRows";
import { MissingPricingAlert } from "./MissingPricingAlert";
import { SyncBanner } from "./SyncBanner";
import { AddPriceButton, PRIMARY_BTN, PricesTable } from "./PricesTable";
import { PageHeader } from "../ai-cost/PageHeader";
import type { Paginated, PriceRow, PriceSummary, PriceTriple } from "./types";

export function AiPricingWidget() {
  const [page, setPage] = useState(1);
  const [summary, setSummary] = useState<Paginated<PriceSummary> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [history, setHistory] = useState<PriceRow[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  // `null` = closed; a string (possibly empty) = open with that model pre-filled.
  const [addModel, setAddModel] = useState<string | null>(null);
  const [addPrices, setAddPrices] = useState<PriceTriple | undefined>(undefined);
  const [alertKey, setAlertKey] = useState(0);
  const [syncKey, setSyncKey] = useState(0);
  const [syncEnabled, setSyncEnabled] = useState(false);

  // Request counters: only the latest request may write state (ignores stale responses).
  const summaryReq = useRef(0);
  const historyReq = useRef(0);

  const loadSummary = useCallback(() => {
    const req = ++summaryReq.current;
    setError(null);
    return fetchPriceSummary(page)
      .then((r) => {
        if (req === summaryReq.current) setSummary(r);
      })
      .catch((e: unknown) => {
        if (req === summaryReq.current)
          setError(e instanceof Error ? e.message : "Failed to load");
      });
  }, [page]);

  const loadHistory = useCallback((model: string) => {
    const req = ++historyReq.current;
    setHistoryError(null);
    return fetchHistory(model)
      .then((r) => {
        if (req === historyReq.current) setHistory(r.results);
      })
      .catch((e: unknown) => {
        if (req === historyReq.current)
          setHistoryError(e instanceof Error ? e.message : "Failed to load history");
      });
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  const toggleHistory = (model: string) => {
    if (expanded === model) {
      historyReq.current++;
      setExpanded(null);
      return;
    }
    setExpanded(model);
    setHistory(null);
    void loadHistory(model);
  };

  // After any price change: refetch the table, the open history and the missing-pricing alert.
  const afterChange = () => {
    void loadSummary();
    if (expanded) void loadHistory(expanded);
    setAlertKey((k) => k + 1);
  };

  const afterSave = () => {
    setAddModel(null);
    setAddPrices(undefined);
    afterChange();
    setSyncKey((k) => k + 1); // the skipped-manual list may no longer apply
  };

  const openAdd = (model?: string) => {
    setAddPrices(undefined);
    setAddModel(model ?? "");
  };
  const openAddWithPrices = (model: string, prices: PriceTriple) => {
    setAddPrices(prices);
    setAddModel(model);
  };

  const totalPages = summary ? Math.max(1, Math.ceil(summary.count / 25)) : 1;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="AI Pricing" sub="Token rates used to calculate AI cost">
        <AddPriceButton label="Add new price" onAddPrice={openAdd} className={PRIMARY_BTN} />
      </PageHeader>

      <SyncBanner
        onChanged={() => setAlertKey((k) => k + 1)}
        onStatus={(st) => setSyncEnabled(st.enabled)}
        onUseLiteLLM={openAddWithPrices}
        refreshKey={syncKey}
      />

      <MissingPricingAlert
        variant="pricing"
        onAddFor={openAdd}
        refreshKey={alertKey}
        syncEnabled={syncEnabled}
      />

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
          onAddPrice={openAdd}
          renderExpanded={() => {
            if (historyError)
              return (
                <div role="alert" className="text-[13px] text-red">
                  {historyError}
                </div>
              );
            if (!history) return <p className="text-[13px] text-muted">Loading history…</p>;
            return <HistoryRows rows={history} onDeleted={afterChange} />;
          }}
        />
      )}

      {summary && summary.count > 25 && (
        <nav aria-label="Pagination" className="flex items-center justify-end gap-2 text-[13px] text-muted">
          <button
            type="button"
            className="px-2.5 py-[5px] rounded-sm border border-line bg-white text-[12.5px] font-medium text-ink enabled:hover:bg-line-soft disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span className="tabular-nums">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="px-2.5 py-[5px] rounded-sm border border-line bg-white text-[12.5px] font-medium text-ink enabled:hover:bg-line-soft disabled:opacity-40"
            disabled={!summary.next}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </nav>
      )}

      {addModel !== null && (
        <AddPriceModal
          open
          initialModel={addModel}
          initialPrices={addPrices}
          onClose={() => setAddModel(null)}
          onSaved={afterSave}
        />
      )}
    </div>
  );
}
