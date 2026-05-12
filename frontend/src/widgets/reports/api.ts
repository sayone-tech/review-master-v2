import type { ReportFilters, StoreReportRow } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
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

export function buildQs(f: ReportFilters): string {
  const p = new URLSearchParams();
  if (f.range !== "all") p.set("range", f.range);
  if (f.range === "custom" && f.date_from) p.set("from", f.date_from);
  if (f.range === "custom" && f.date_to) p.set("to", f.date_to);
  if (f.reply_status !== "all") p.set("reply_status", f.reply_status);
  if (f.sentiment !== "all") p.set("sentiment", f.sentiment);
  return p.toString();
}

export async function fetchStoreReport(
  filters: ReportFilters,
): Promise<StoreReportRow[]> {
  const qs = buildQs(filters);
  const resp = await fetch(`/api/v1/reports/stores/${qs ? `?${qs}` : ""}`, {
    credentials: "same-origin",
  });
  return handle<StoreReportRow[]>(resp);
}
