// Phase 21-04 — Audit log API client.
// Calls GET /api/v1/audit-logs/ (cursor-paginated, org/staff-scoped).

import type { AuditLogResponse, FilterParams } from "./types";

const BASE_URL = "/api/v1/audit-logs/";

function buildUrl(params: FilterParams, pageSize: number): string {
  const u = new URLSearchParams();
  if (params.entity_type) u.set("entity_type", params.entity_type);
  if (params.actor) u.set("actor", params.actor);
  if (params.date_from) u.set("date_from", params.date_from);
  if (params.date_to) u.set("date_to", params.date_to);
  u.set("page_size", String(pageSize));
  const qs = u.toString();
  return qs ? `${BASE_URL}?${qs}` : BASE_URL;
}

/**
 * Fetch a page of audit logs.
 *
 * @param params  Filter parameters (entity_type, actor, date_from, date_to).
 * @param pageSize Page size for cursor pagination (default 50).
 * @param cursor  Full cursor URL from a previous response's `next`/`previous` field.
 *                When provided, params/pageSize are ignored — the cursor URL already
 *                encodes the query string the server emitted.
 */
export async function fetchAuditLogs(
  params: FilterParams,
  pageSize: number = 50,
  cursor?: string,
): Promise<AuditLogResponse> {
  const url = cursor ?? buildUrl(params, pageSize);
  const resp = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return (await resp.json()) as AuditLogResponse;
}
