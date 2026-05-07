import type {
  DashboardFilters,
  HighlightsResponse,
  KpisResponse,
  SentimentResponse,
  TopPerformingResponse,
  YourStoreResponse,
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

function buildFullQs(f: DashboardFilters): string {
  const p = new URLSearchParams();
  if (f.region_id) p.set("region", String(f.region_id));
  if (f.shop_id) p.set("store", String(f.shop_id));
  p.set("range", f.range);
  if (f.range === "custom" && f.date_from) p.set("from", f.date_from);
  if (f.range === "custom" && f.date_to) p.set("to", f.date_to);
  return p.toString();
}

function buildDateOnlyQs(
  f: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
): string {
  const p = new URLSearchParams();
  p.set("range", f.range);
  if (f.range === "custom" && f.date_from) p.set("from", f.date_from);
  if (f.range === "custom" && f.date_to) p.set("to", f.date_to);
  return p.toString();
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = (await resp.json()) as Record<string, unknown>;
      const raw = body["detail"] ?? body["error"] ?? JSON.stringify(body);
      detail = typeof raw === "string" ? raw : JSON.stringify(raw);
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export async function fetchKpis(filters: DashboardFilters): Promise<KpisResponse> {
  const r = await fetch(`/api/v1/dashboard/kpis/?${buildFullQs(filters)}`, {
    credentials: "same-origin",
  });
  return handle<KpisResponse>(r);
}

export async function fetchSentiment(
  filters: DashboardFilters,
): Promise<SentimentResponse> {
  const r = await fetch(
    `/api/v1/dashboard/sentiment-distribution/?${buildFullQs(filters)}`,
    { credentials: "same-origin" },
  );
  return handle<SentimentResponse>(r);
}

export async function fetchTopPerforming(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
): Promise<TopPerformingResponse> {
  const r = await fetch(
    `/api/v1/dashboard/top-performing/?${buildDateOnlyQs(filters)}`,
    { credentials: "same-origin" },
  );
  return handle<TopPerformingResponse>(r);
}

export async function fetchHighlights(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
): Promise<HighlightsResponse> {
  const r = await fetch(
    `/api/v1/dashboard/highlights/?${buildDateOnlyQs(filters)}`,
    { credentials: "same-origin" },
  );
  return handle<HighlightsResponse>(r);
}

export async function fetchYourStore(
  filters: Pick<DashboardFilters, "range" | "date_from" | "date_to">,
): Promise<YourStoreResponse> {
  const r = await fetch(
    `/api/v1/dashboard/your-store/?${buildDateOnlyQs(filters)}`,
    { credentials: "same-origin" },
  );
  return handle<YourStoreResponse>(r);
}
