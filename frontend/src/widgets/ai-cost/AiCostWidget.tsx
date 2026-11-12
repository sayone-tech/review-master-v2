import { useCallback, useEffect, useState } from "react";
import { fetchOrganisations, fetchSummary, ApiError } from "./api";
import { formatUpdatedAgo } from "./format";
import { KpiRow } from "./KpiRow";
import { MissingPricingAlert } from "../ai-pricing/MissingPricingAlert";
import { OrgDetail } from "./OrgDetail";
import { SyncCaveat } from "./SyncCaveat";
import { OrgTable } from "./OrgTable";
import { RangeFilter } from "./RangeFilter";
import {
  readFilters,
  readListState,
  writeFilters,
  writeUrlState,
  type ListState,
} from "./urlState";
import {
  PAGE_SIZES,
  type CostFilters,
  type CostSummaryResponse,
  type OrgListResponse,
} from "./types";


const ORG_PATH = /^\/admin\/ai-cost\/organisations\/(\d+)\/?$/;

function orgIdFromPath(): number | null {
  const m = ORG_PATH.exec(window.location.pathname);
  return m ? Number(m[1]) : null;
}

function PlatformView({
  filters,
  list,
  onFilters,
  onList,
  onOpen,
}: {
  filters: CostFilters;
  list: ListState;
  onFilters: (f: CostFilters) => void;
  onList: (l: ListState) => void;
  onOpen: (orgId: number) => void;
}) {
  const { page, pageSize, sort } = list;
  const [summary, setSummary] = useState<CostSummaryResponse | null>(null);
  const [orgs, setOrgs] = useState<OrgListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const setPage = (fn: (p: number) => number) => onList({ ...list, page: fn(page) });

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRangeError(null);
    Promise.all([fetchSummary(filters), fetchOrganisations(filters, { page, pageSize, sort })])
      .then(([s, o]) => {
        if (cancelled) return;
        setSummary(s);
        setOrgs(o);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 400) setRangeError(e.message);
        else setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, page, pageSize, sort]);

  useEffect(() => load(), [load]);

  const changeFilters = (f: CostFilters) => {
    onFilters(f);
  };

  const hasAnyUsage = summary?.has_any_usage !== false;
  const empty = !loading && !error && !rangeError && summary && orgs && orgs.count === 0;
  const totalPages = orgs ? Math.max(1, Math.ceil(orgs.count / pageSize)) : 1;

  return (
    <>
      <RangeFilter filters={filters} onChange={changeFilters} error={rangeError} />

      {error && (
        <div role="alert" className="text-[13px] text-red-600">
          {error}{" "}
          <button type="button" className="underline" onClick={() => load()}>
            Retry
          </button>
        </div>
      )}

      <MissingPricingAlert variant="cost-explorer" />

      {summary && !rangeError && <KpiRow totals={summary.totals} />}

      {empty &&
        (hasAnyUsage ? (
          <div className="bg-white border border-line rounded-card p-8 text-center">
            <p className="text-ink font-medium">No AI usage in this period</p>
            <p className="text-[13px] text-muted">Try widening the date range.</p>
          </div>
        ) : (
          <div className="bg-white border border-line rounded-card p-8 text-center text-muted">
            No AI calls yet. Costs will appear here as reviews are enriched.
          </div>
        ))}

      {orgs && orgs.count > 0 && !rangeError && (
        <div className="bg-white border border-line rounded-card overflow-hidden">
          <OrgTable
            rows={orgs.results}
            sort={sort}
            onSort={(s) => {
              onList({ ...list, page: 1, sort: s });
            }}
            onOpen={onOpen}
            query={writeFilters(filters)}
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
                  onList({ ...list, page: 1, pageSize: Number(e.target.value) });
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
                disabled={!orgs.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </nav>
        </div>
      )}

      <p className="text-[12px] text-muted">
        {summary && <span>{formatUpdatedAgo(summary.generated_at)} · </span>}
        <SyncCaveat />
      </p>
    </>
  );
}

export function AiCostWidget({ orgId: initialOrgId }: { orgId: number | null }) {
  const [orgId, setOrgId] = useState<number | null>(initialOrgId);
  const [filters, setFilters] = useState<CostFilters>(() => readFilters(window.location.search));
  const [list, setList] = useState<ListState>(() => readListState(window.location.search));

  useEffect(() => {
    const onPop = () => {
      setOrgId(orgIdFromPath());
      setFilters(readFilters(window.location.search));
      setList(readListState(window.location.search));
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // The list state is only part of the URL on the platform view.
  const sync = (f: CostFilters, l: ListState, id: number | null) => {
    const query = id === null ? writeUrlState(f, l) : writeFilters(f);
    window.history.replaceState(null, "", `${window.location.pathname}${query}`);
  };

  const changeFilters = (f: CostFilters) => {
    const l = { ...list, page: 1 };
    sync(f, l, orgId);
    setFilters(f);
    setList(l);
  };

  const changeList = (l: ListState) => {
    sync(filters, l, orgId);
    setList(l);
  };

  const openOrg = (id: number) => {
    window.history.pushState(null, "", `/admin/ai-cost/organisations/${id}/${writeFilters(filters)}`);
    setOrgId(id);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[20px] font-semibold text-ink">AI Cost Explorer</h1>
        <p className="text-[13px] text-muted">Platform-wide OpenAI spend</p>
      </div>
      {orgId === null ? (
        <PlatformView
          filters={filters}
          list={list}
          onFilters={changeFilters}
          onList={changeList}
          onOpen={openOrg}
        />
      ) : (
        <OrgDetail
          orgId={orgId}
          filters={filters}
          onFilters={changeFilters}
          onBack={() => {
            window.history.pushState(null, "", `/admin/ai-cost/${writeUrlState(filters, list)}`);
            setOrgId(null);
          }}
        />
      )}
    </div>
  );
}
