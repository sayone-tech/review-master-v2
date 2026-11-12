import type {
  CostFilters,
  CostSummaryResponse,
  ModelListResponse,
  OrgListResponse,
  ShopListResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const BASE = "/api/v1/superadmin/ai-cost";

export function rangeParams(f: CostFilters): URLSearchParams {
  const p = new URLSearchParams();
  p.set("range", f.range);
  if (f.range === "custom") {
    if (f.from) p.set("from", f.from);
    if (f.to) p.set("to", f.to);
  }
  return p;
}

export async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url, { credentials: "same-origin" });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as Record<string, unknown>;
      const raw = body["detail"] ?? body["error"];
      if (Array.isArray(raw)) detail = raw.map(String).join(" ");
      else if (typeof raw === "string") detail = raw;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export function fetchSummary(f: CostFilters): Promise<CostSummaryResponse> {
  return getJson(`${BASE}/summary/?${rangeParams(f).toString()}`);
}

export function fetchOrganisations(
  f: CostFilters,
  opts: { page: number; pageSize: number; sort: string },
): Promise<OrgListResponse> {
  const p = rangeParams(f);
  p.set("page", String(opts.page));
  p.set("page_size", String(opts.pageSize));
  p.set("sort", opts.sort);
  return getJson(`${BASE}/organisations/?${p.toString()}`);
}

export function fetchOrgSummary(orgId: number, f: CostFilters): Promise<CostSummaryResponse> {
  return getJson(`${BASE}/organisations/${orgId}/summary/?${rangeParams(f).toString()}`);
}

export function fetchOrgShops(
  orgId: number,
  f: CostFilters,
  opts: { page: number; pageSize: number; sort: string },
): Promise<ShopListResponse> {
  const p = rangeParams(f);
  p.set("page", String(opts.page));
  p.set("page_size", String(opts.pageSize));
  p.set("sort", opts.sort);
  return getJson(`${BASE}/organisations/${orgId}/shops/?${p.toString()}`);
}

export function fetchOrgModels(orgId: number, f: CostFilters): Promise<ModelListResponse> {
  return getJson(`${BASE}/organisations/${orgId}/models/?${rangeParams(f).toString()}`);
}
