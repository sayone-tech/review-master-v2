import { useCallback, useEffect, useState } from "react";
import { fetchOrganisations, fetchSummary, ApiError } from "./api";
import { formatUpdatedAgo } from "./format";
import { KpiRow } from "./KpiRow";
import { MissingPricingAlert } from "../ai-pricing/MissingPricingAlert";
import { OrgDetail } from "./OrgDetail";
import { SyncCaveat } from "./SyncCaveat";
import { OrgTable } from "./OrgTable";
import { CostFilterCard } from "./CostFilterCard";
import { Pagination } from "./Pagination";
import {
  readFilters,
  readListState,
  writeFilters,
  writeUrlState,
  type ListState,
} from "./urlState";
import {
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

  return (
    <>
      <CostFilterCard filters={filters} onApply={changeFilters} serverError={rangeError} />

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
          <Pagination
            page={page}
            pageSize={pageSize}
            count={orgs.count}
            onPage={(p) => onList({ ...list, page: p })}
            onPageSize={(n) => onList({ ...list, page: 1, pageSize: n })}
          />
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
