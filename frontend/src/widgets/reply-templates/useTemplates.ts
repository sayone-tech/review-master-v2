import { useState, useEffect, useCallback } from "react";
import type { TemplateRow } from "./types";
import { listTemplates } from "./api";

export function useTemplates(initialRows: TemplateRow[]) {
  const [rows, setRows] = useState<TemplateRow[]>(initialRows);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listTemplates();
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handler = () => void refresh();
    window.addEventListener("template:refresh", handler);
    return () => window.removeEventListener("template:refresh", handler);
  }, [refresh]);

  return { rows, loading, refresh };
}
