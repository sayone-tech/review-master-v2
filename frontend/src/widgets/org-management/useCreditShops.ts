import { useCallback, useEffect, useRef, useState } from "react";
import { listCreditShops, type CreditShopListResponse } from "./creditsApi";

const SEARCH_DEBOUNCE_MS = 300;

export interface UseCreditShops {
  data: CreditShopListResponse | null;
  loading: boolean;
  error: boolean;
  search: string;
  setSearch: (v: string) => void;
  page: number;
  setPage: (n: number) => void;
  reload: () => Promise<void>;
}

/** Debounced, abortable, paginated shop credit list for one organisation.
 * State is cleared when orgId becomes null (modal closed). */
export function useCreditShops(orgId: number | null): UseCreditShops {
  const [search, setSearchState] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPageState] = useState(1);
  const [data, setData] = useState<CreditShopListResponse | null>(null);
  const [loading, setLoading] = useState(orgId !== null);
  const [error, setError] = useState(false);

  const controller = useRef<AbortController | null>(null);
  const requestId = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const run = useCallback(async (): Promise<void> => {
    if (orgId === null) return;
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    const id = ++requestId.current;
    setLoading(true);
    setError(false);
    try {
      const res = await listCreditShops(orgId, { search: debounced, page }, c.signal);
      // A slower, older response must never replace a newer one.
      if (id !== requestId.current) return;
      setData(res);
    } catch {
      if (id !== requestId.current || c.signal.aborted) return;
      setError(true);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [orgId, debounced, page]);

  const runRef = useRef(run);
  runRef.current = run;

  useEffect(() => {
    void run();
  }, [run]);

  // Modal closed: drop everything so the next open starts clean.
  useEffect(() => {
    if (orgId !== null) return;
    controller.current?.abort();
    requestId.current += 1;
    if (timer.current) clearTimeout(timer.current);
    setSearchState("");
    setDebounced("");
    setPageState(1);
    setData(null);
    setError(false);
    setLoading(false);
  }, [orgId]);

  useEffect(
    () => () => {
      controller.current?.abort();
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const setSearch = useCallback((v: string) => {
    setSearchState(v);
    if (timer.current) clearTimeout(timer.current);
    if (v.trim() === "") {
      setDebounced("");
      setPageState(1);
      return;
    }
    timer.current = setTimeout(() => {
      setDebounced(v);
      setPageState(1);
    }, SEARCH_DEBOUNCE_MS);
  }, []);

  const setPage = useCallback((n: number) => setPageState(n), []);
  const reload = useCallback(() => runRef.current(), []);

  return { data, loading, error, search, setSearch, page, setPage, reload };
}
