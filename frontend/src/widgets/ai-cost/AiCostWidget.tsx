import { useCallback, useEffect, useRef, useState } from "react";
import { fetchOrganisations, fetchSummary, ApiError } from "./api";
import { applyCostCrumb } from "./breadcrumb";
import { formatUpdatedAgo } from "./format";
import { SummaryStrip } from "./SummaryStrip";
import { MissingPricingAlert } from "../ai-pricing/MissingPricingAlert";
import { OrgDetail } from "./OrgDetail";
import { SyncCaveat } from "./SyncCaveat";
import { OrgTable } from "./OrgTable";
import { CostFilterCard } from "./CostFilterCard";
import { PageHeader, TableCard } from "./PageHeader";
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
  onOpen: (orgId: number, name: string | null) => void;
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
      <PageHeader sub="OpenAI spend across all organisations">
        <CostFilterCard filters={filters} onApply={changeFilters} serverError={rangeError} />
      </PageHeader>

      {error && (
        <div role="alert" className="text-[13px] text-red">
          {error}{" "}
          <button type="button" className="underline" onClick={() => load()}>
            Retry
          </button>
        </div>
      )}

      <MissingPricingAlert variant="cost-explorer" />

      {summary && !rangeError && <SummaryStrip totals={summary.totals} />}

      {empty &&
        (hasAnyUsage ? (
          <div className="rounded-card border border-line bg-white p-10 text-center">
            <p className="font-medium text-ink">No AI usage in this period</p>
            <p className="mt-1 text-[13.5px] text-muted">Try a wider date range.</p>
          </div>
        ) : (
          <div className="rounded-card border border-line bg-white p-10 text-center">
            <p className="font-medium text-ink">No AI calls yet</p>
            <p className="mt-1 text-[13.5px] text-muted">Costs appear here as reviews are enriched.</p>
          </div>
        ))}

      {orgs && orgs.count > 0 && !rangeError && (
        <TableCard title="Organisations" meta={summary && formatUpdatedAgo(summary.generated_at)}>
          <OrgTable
            rows={orgs.results}
            sort={sort}
            totalCost={summary ? Number(summary.totals.cost) : 0}
            onSort={(s) => {
              onList({ ...list, page: 1, sort: s });
            }}
            onOpen={(id) => onOpen(id, orgs.results.find((o) => o.organisation_id === id)?.name ?? null)}
            query={writeFilters(filters)}
          />
          <Pagination
            page={page}
            pageSize={pageSize}
            count={orgs.count}
            onPage={(p) => onList({ ...list, page: p })}
            onPageSize={(n) => onList({ ...list, page: 1, pageSize: n })}
          />
        </TableCard>
      )}

      <p className="text-[12px] text-muted">
        <SyncCaveat />
      </p>
    </>
  );
}

export function AiCostWidget({
  orgId: initialOrgId,
  orgName: initialOrgName = null,
}: {
  orgId: number | null;
  /** Server-rendered organisation name for the breadcrumb (detail route only). */
  orgName?: string | null;
}) {
  const [orgId, setOrgId] = useState<number | null>(initialOrgId);
  const [orgName, setOrgName] = useState<string | null>(initialOrgId === null ? null : initialOrgName);
  const rootRef = useRef<HTMLDivElement>(null);
  const [filters, setFilters] = useState<CostFilters>(() => readFilters(window.location.search));
  const [list, setList] = useState<ListState>(() => readListState(window.location.search));

  useEffect(() => {
    const onPop = () => {
      setOrgId(orgIdFromPath());
      setOrgName(null);
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

  const openOrg = (id: number, name: string | null) => {
    window.history.pushState(null, "", `/admin/ai-cost/organisations/${id}/${writeFilters(filters)}`);
    setOrgId(id);
    setOrgName(name);
  };

  const goBack = useCallback(() => {
    window.history.pushState(null, "", `/admin/ai-cost/${writeUrlState(filters, list)}`);
    setOrgId(null);
  }, [filters, list]);

  // Top-bar breadcrumb. Turbo resets the (permanent) top bar from data-page-title on each visit,
  // so re-apply after turbo:load while this widget is still on the page.
  useEffect(() => {
    const apply = () =>
      applyCostCrumb(
        orgId === null
          ? null
          : { name: orgName, href: `/admin/ai-cost/${writeUrlState(filters, list)}`, onBack: goBack },
      );
    let cleanup = apply();
    const onTurboLoad = () => {
      if (!rootRef.current?.isConnected) return;
      cleanup();
      cleanup = apply();
    };
    document.addEventListener("turbo:load", onTurboLoad);
    return () => {
      document.removeEventListener("turbo:load", onTurboLoad);
      cleanup();
    };
  }, [orgId, orgName, filters, list, goBack]);

  return (
    <div ref={rootRef} className="space-y-4">
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
          onBack={goBack}
          initialName={orgName}
          onOrgName={setOrgName}
        />
      )}
    </div>
  );
}
