import { useCallback, useEffect, useState } from "react";
import { listOrgs } from "./api";
import type { OrgRow } from "./types";

function readInitialRows(): OrgRow[] {
  const el = document.getElementById("org-data");
  if (!el || !el.textContent) return [];
  try {
    return JSON.parse(el.textContent) as OrgRow[];
  } catch {
    return [];
  }
}

function refreshQueryString(): string {
  // Preserve search/status/type/per_page, strip page (post-mutation reset to page 1).
  const current = new URLSearchParams(window.location.search);
  current.delete("page");
  return current.toString();
}

export interface UseOrgsApi {
  rows: OrgRow[];
  loading: boolean;
  refresh: () => Promise<void>;
  replaceRow: (row: OrgRow) => void;
}

export function useOrgs(): UseOrgsApi {
  const [rows, setRows] = useState<OrgRow[]>(() => readInitialRows());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await listOrgs(refreshQueryString());
      setRows(resp.results);
    } finally {
      setLoading(false);
    }
  }, []);

  const replaceRow = useCallback((row: OrgRow) => {
    setRows((prev) => prev.map((r) => (r.id === row.id ? row : r)));
  }, []);

  // Re-render pipeline for debugging / future hot-reload; no-op effect.
  useEffect(() => {
    // Intentionally empty — rows seed from blob on first render.
  }, []);

  return { rows, loading, refresh, replaceRow };
}
