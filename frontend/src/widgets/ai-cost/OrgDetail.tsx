import { useEffect, useState } from "react";
import { ApiError, fetchOrgModels, fetchOrgShops, fetchOrgSummary } from "./api";
import { CAVEAT } from "./AiCostWidget";
import { formatUpdatedAgo, titleCase } from "./format";
import { KpiRow } from "./KpiRow";
import { ModelTable } from "./ModelTable";
import { RangeFilter } from "./RangeFilter";
import { ShopTable } from "./ShopTable";
import { writeFilters } from "./urlState";
import {
  PAGE_SIZES,
  type CostFilters,
  type CostSummaryResponse,
  type ModelListResponse,
  type ShopListResponse,
} from "./types";

interface Props {
  orgId: number;
  filters: CostFilters;
  onFilters: (f: CostFilters) => void;
  onBack: () => void;
}

function BackLink({ filters, onBack }: { filters: CostFilters; onBack: () => void }) {
  return (
    <a
      href={`/admin/ai-cost/${writeFilters(filters)}`}
      className="text-[13px] text-muted hover:text-ink hover:underline"
      onClick={(e) => {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        e.preventDefault();
        onBack();
      }}
    >
      ← Back to AI Cost
    </a>
  );
}

export function OrgDetail({ orgId, filters, onFilters, onBack }: Props) {
  const [summary, setSummary] = useState<CostSummaryResponse | null>(null);
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [shops, setShops] = useState<ShopListResponse | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [sort, setSort] = useState("-cost");

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 404) setNotFound(true);
    else if (e instanceof ApiError && e.status === 400) setRangeError(e.message);
    else setError(e instanceof Error ? e.message : "Failed to load");
  };

  // Header + models: independent of paging/sort.
  useEffect(() => {
    let cancelled = false;
    setNotFound(false);
    setError(null);
    setRangeError(null);
    Promise.all([fetchOrgSummary(orgId, filters), fetchOrgModels(orgId, filters)])
      .then(([s, m]) => {
        if (cancelled) return;
        setSummary(s);
        setModels(m);
      })
      .catch((e: unknown) => {
        if (!cancelled) fail(e);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId, filters, retryKey]);

  useEffect(() => {
    let cancelled = false;
    fetchOrgShops(orgId, filters, { page, pageSize, sort })
      .then((s) => {
        if (!cancelled) setShops(s);
      })
      .catch((e: unknown) => {
        if (!cancelled) fail(e);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId, filters, page, pageSize, sort, retryKey]);

  const changeFilters = (f: CostFilters) => {
    setPage(1);
    onFilters(f);
  };

  if (notFound) {
    return (
      <div className="space-y-4">
        <BackLink filters={filters} onBack={onBack} />
        <div className="bg-white border border-line rounded-card p-8 text-center text-muted">
          Organisation not found
        </div>
      </div>
    );
  }

  const org = summary?.organisation;
  const empty = !!summary && !rangeError && summary.totals.calls === 0;
  const totalPages = shops ? Math.max(1, Math.ceil(shops.count / pageSize)) : 1;

  return (
    <div className="space-y-4">
      <div>
        <BackLink filters={filters} onBack={onBack} />
        {org && (
          <>
            <h2 className="mt-1 text-[18px] font-semibold text-ink">{org.name}</h2>
            <p className="text-[13px] text-muted">
              {titleCase(org.org_type)} · {org.shop_count} {org.shop_count === 1 ? "shop" : "shops"} ·{" "}
              {summary.totals.active_shops} active in date range
            </p>
          </>
        )}
      </div>

      <RangeFilter filters={filters} onChange={changeFilters} error={rangeError} />

      {error && (
        <div role="alert" className="text-[13px] text-red-600">
          {error}{" "}
          <button type="button" className="underline" onClick={() => setRetryKey((k) => k + 1)}>
            Retry
          </button>
        </div>
      )}

      {summary && !rangeError && <KpiRow
          totals={summary.totals}
          costFooter={`Across ${summary.totals.active_shops} active ${summary.totals.active_shops === 1 ? "shop" : "shops"}`}
        />}

      {empty && (
        <div className="bg-white border border-line rounded-card p-8 text-center">
          <p className="text-muted">No AI usage for this organisation in the selected period</p>
          <a
            href={`/admin/ai-cost/organisations/${orgId}/${writeFilters({ range: "this_month" })}`}
            className="text-[13px] text-ink underline"
            onClick={(e) => {
              if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
              e.preventDefault();
              changeFilters({ range: "this_month" });
            }}
          >
            Reset filter
          </a>
        </div>
      )}

      {!empty && !rangeError && shops && (
        <div className="bg-white border border-line rounded-card overflow-hidden">
          <ShopTable
            rows={shops.results}
            unattributed={shops.unattributed}
            sort={sort}
            onSort={(s) => {
              setPage(1);
              setSort(s);
            }}
          />
          <nav
            aria-label="Pagination"
            className="flex items-center justify-between px-4 py-3 border-t border-line bg-[#FBFBFB] text-[12px] text-muted"
          >
            <label className="flex items-center gap-2">
              Rows per page
              <select
                className="h-8 rounded-sm border border-line bg-white px-1"
                value={pageSize}
                onChange={(e) => {
                  setPage(1);
                  setPageSize(Number(e.target.value));
                }}
              >
                {PAGE_SIZES.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-2">
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
                disabled={!shops.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </nav>
        </div>
      )}

      {!empty && !rangeError && models && models.results.length > 0 && (
        <section className="bg-white border border-line rounded-card overflow-hidden">
          <h3 className="px-4 py-3 text-[14px] font-semibold text-ink">Cost by Model</h3>
          <ModelTable rows={models.results} />
        </section>
      )}

      <p className="text-[12px] text-muted">
        {summary && <span>{formatUpdatedAgo(summary.generated_at)} · </span>}
        {CAVEAT}
      </p>
    </div>
  );
}
