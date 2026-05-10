import { handle, headers } from "./api";
import type { TargetCreatePayload, TargetRow, TargetUpdatePayload } from "./types";

export { ApiError } from "./api";

export async function listTargets(shopId: number): Promise<TargetRow[]> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    credentials: "same-origin",
    headers: headers("GET"),
  });
  return handle<TargetRow[]>(resp);
}

export async function createTarget(
  shopId: number,
  payload: TargetCreatePayload,
): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/`, {
    method: "POST",
    credentials: "same-origin",
    headers: headers("POST"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function patchTarget(
  shopId: number,
  targetId: number,
  payload: TargetUpdatePayload,
): Promise<TargetRow> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: headers("PATCH"),
    body: JSON.stringify(payload),
  });
  return handle<TargetRow>(resp);
}

export async function deleteTarget(shopId: number, targetId: number): Promise<void> {
  const resp = await fetch(`/api/v1/shops/${shopId}/targets/${targetId}/`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: headers("DELETE"),
  });
  return handle<void>(resp);
}
