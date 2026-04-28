import { useState, useEffect, useCallback } from "react";
import type { RegionRow } from "./types";
import { listRegions } from "./api";

export function useRegions(initialRows: RegionRow[]) {
  const [rows, setRows] = useState<RegionRow[]>(initialRows);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRegions();
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener("region:refresh", handler);
    return () => window.removeEventListener("region:refresh", handler);
  }, [refresh]);

  return { rows, loading, refresh };
}
