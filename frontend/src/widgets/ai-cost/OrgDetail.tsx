import { useEffect, useState } from "react";
import { ApiError, fetchOrgModels, fetchOrgShops, fetchOrgSummary } from "./api";
import { SyncCaveat } from "./SyncCaveat";
import { formatUpdatedAgo, titleCase } from "./format";
import { SummaryStrip } from "./SummaryStrip";
import { ModelTable } from "./ModelTable";
import { CostFilterCard } from "./CostFilterCard";
import { NeutralBadge, PageHeader, TableCard } from "./PageHeader";
import { Pagination } from "./Pagination";
import { ShopTable } from "./ShopTable";
import { writeFilters } from "./urlState";
import {
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
  /** Name known before the summary loads (server-rendered), shown in the header meanwhile. */
  initialName?: string | null;
  /** Reports the loaded organisation name, or null when it does not exist (for the breadcrumb). */
  onOrgName?: (name: string | null) => void;
}

const isPlainClick = (e: React.MouseEvent) =>
  e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;

export function OrgDetail({ orgId, filters, onFilters, onBack, initialName = null, onOrgName }: Props) {
  const [summary, setSummary] = useState<CostSummaryResponse | null>(null);
  const [models, setModels] = useState<ModelListResponse | null>(null);
  const [shops, setShops] = useState<ShopListResponse | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [sort, setSort] = useState("-cost");

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 404) {
      setNotFound(true);
      onOrgName?.(null);
    } else if (e instanceof ApiError && e.status === 400) setRangeError(e.message);
    else setError(e instanceof Error ? e.message : "Failed to load");
  };

  // Header + models: independent of paging/sort.
  useEffect(() => {
    let cancelled = false;
    setNotFound(false);
    setError(null);
    setRangeError(null);
    setModelsError(null);
    fetchOrgSummary(orgId, filters)
      .then((s) => {
        if (cancelled) return;
        setSummary(s);
        if (s.organisation) onOrgName?.(s.organisation.name);
      })
      .catch((e: unknown) => {
        if (!cancelled) fail(e);
      });
    fetchOrgModels(orgId, filters)
      .then((m) => {
        if (!cancelled) setModels(m);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && (e.status === 404 || e.status === 400)) fail(e);
        else setModelsError(e instanceof Error ? e.message : "Failed to load models");
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
      <div className="rounded-card border border-line bg-white p-10 text-center">
        <p className="text-[16px] font-semibold text-ink">Organisation not found</p>
        <p className="mt-1 text-[13.5px] text-muted">It may have been deleted, or the link is wrong.</p>
        <a
          href={`/admin/ai-cost/${writeFilters(filters)}`}
          className="mt-4 inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          onClick={(e) => {
            if (!isPlainClick(e)) return;
            e.preventDefault();
            onBack();
          }}
        >
          Back to AI Cost
        </a>
      </div>
    );
  }

  const org = summary?.organisation;
  const empty = !!summary && !rangeError && summary.totals.calls === 0;
  const totalCost = summary ? Number(summary.totals.cost) : 0;
  const shopCount = (n: number) => `${n} ${n === 1 ? "shop" : "shops"}`;

  return (
    <div className="space-y-4">
      <PageHeader
        title={org?.name ?? initialName ?? " "}
        badge={org && <NeutralBadge>{titleCase(org.org_type)}</NeutralBadge>}
        sub={
          org && summary
            ? `${shopCount(org.shop_count)}, ${summary.totals.active_shops} active in this period`
            : undefined
        }
      >
        <CostFilterCard filters={filters} onApply={changeFilters} serverError={rangeError} />
      </PageHeader>

      {error && (
        <div role="alert" className="text-[13px] text-red">
          {error}{" "}
          <button type="button" className="underline" onClick={() => setRetryKey((k) => k + 1)}>
            Retry
          </button>
        </div>
      )}

      {summary && !rangeError && (
        <SummaryStrip
          totals={summary.totals}
          costFooter={`Across ${summary.totals.active_shops} active ${summary.totals.active_shops === 1 ? "shop" : "shops"}`}
        />
      )}

      {empty && (
        <div className="rounded-card border border-line bg-white p-10 text-center">
          <p className="font-medium text-ink">No AI usage for this organisation in the selected period</p>
          <a
            href={`/admin/ai-cost/organisations/${orgId}/${writeFilters({ range: "this_month" })}`}
            className="mt-1 inline-block text-[13.5px] text-muted underline underline-offset-2 hover:text-ink"
            onClick={(e) => {
              if (!isPlainClick(e)) return;
              e.preventDefault();
              changeFilters({ range: "this_month" });
            }}
          >
            Reset filter
          </a>
        </div>
      )}

      {!empty && !rangeError && shops && (
        <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3">
          <TableCard
              title="Shops"
              meta={summary && formatUpdatedAgo(summary.generated_at)}
              className="xl:col-span-2"
            >
              <ShopTable
                rows={shops.results}
                unattributed={shops.unattributed}
                sort={sort}
                totalCost={totalCost}
                onSort={(s) => {
                  setPage(1);
                  setSort(s);
                }}
              />
              <Pagination
                page={page}
                pageSize={pageSize}
                count={shops.count}
                onPage={setPage}
                onPageSize={(n) => {
                  setPage(1);
                  setPageSize(n);
                }}
              />
          </TableCard>
          {modelsError ? (
            <TableCard title="Cost by model">
              <p role="alert" className="px-4 py-3 text-[13px] text-red">
                Could not load model costs: {modelsError}{" "}
                <button type="button" className="underline" onClick={() => setRetryKey((k) => k + 1)}>
                  Retry
                </button>
              </p>
            </TableCard>
          ) : (
            models &&
            models.results.length > 0 && (
              <TableCard title="Cost by model">
                <ModelTable rows={models.results} />
              </TableCard>
            )
          )}
        </div>
      )}

      <p className="text-[12px] text-muted">
        <SyncCaveat />
      </p>
    </div>
  );
}
