import { useCallback, useState } from "react";

/**
 * Page state for the book. Page 0 is the cover, 1..total are the steps in
 * between (spreads, or single pages on phones), total + 1 is the end page.
 */
export function useBook(total: number) {
  const [rawPage, setPage] = useState(0);
  const last = total + 1;
  const clamp = useCallback((p: number) => Math.max(0, Math.min(last, p)), [last]);
  const page = clamp(rawPage);
  const next = useCallback(() => setPage((p) => clamp(clamp(p) + 1)), [clamp]);
  const prev = useCallback(() => setPage((p) => clamp(clamp(p) - 1)), [clamp]);
  const jump = useCallback((target: number) => setPage(clamp(target)), [clamp]);
  return { page, next, prev, jump };
}
