// Phase 21-04 — useAuditLog hook.
// Manages cursor state, filters, URL param sync, loading, error, and one-row-expanded.

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAuditLogs } from "./api";
import type { AuditLogRow, FilterParams } from "./types";

const DEFAULT_PAGE_SIZE = 50;
const DEFAULT_DATE_WINDOW_DAYS = 30;

function isoDate(d: Date): string {
  // YYYY-MM-DD in UTC — server compares against created_at::date.
  return d.toISOString().split("T")[0];
}

function defaultDateRange(): { date_from: string; date_to: string } {
  const today = new Date();
  const from = new Date(Date.now() - DEFAULT_DATE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  return { date_from: isoDate(from), date_to: isoDate(today) };
}

function readUrlFilters(): FilterParams {
  if (typeof window === "undefined") return defaultDateRange();
  const params = new URLSearchParams(window.location.search);
  const entity_type = params.get("entity_type") ?? undefined;
  const actor = params.get("actor") ?? undefined;
  const date_from = params.get("date_from") ?? undefined;
  const date_to = params.get("date_to") ?? undefined;
  const hasAnyDate = Boolean(date_from || date_to);
  const defaults = defaultDateRange();
  return {
    entity_type: entity_type || undefined,
    actor: actor || undefined,
    date_from: hasAnyDate ? date_from : defaults.date_from,
    date_to: hasAnyDate ? date_to : defaults.date_to,
  };
}

function writeUrlFilters(filters: FilterParams): void {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams();
  if (filters.entity_type) params.set("entity_type", filters.entity_type);
  if (filters.actor) params.set("actor", filters.actor);
  if (filters.date_from) params.set("date_from", filters.date_from);
  if (filters.date_to) params.set("date_to", filters.date_to);
  const qs = params.toString();
  const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.pushState({}, "", url);
}

export interface UseAuditLogResult {
  rows: AuditLogRow[];
  loading: boolean;
  error: string | null;
  filters: FilterParams;
  pageSize: number;
  hasNext: boolean;
  hasPrev: boolean;
  goNext: () => void;
  goPrev: () => void;
  applyFilters: (next: FilterParams) => void;
  resetFilters: () => void;
  changePageSize: (n: number) => void;
  refetch: () => void;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
}

export function useAuditLog(): UseAuditLogResult {
  const [filters, setFilters] = useState<FilterParams>(() => readUrlFilters());
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [cursor, setCursor] = useState<string | null>(null);
  const prevCursorsRef = useRef<(string | null)[]>([]);
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [prevUrl, setPrevUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAuditLogs(filters, pageSize, cursor ?? undefined)
      .then((resp) => {
        if (cancelled) return;
        setRows(resp.results);
        setNextUrl(resp.next);
        setPrevUrl(resp.previous);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        setRows([]);
        setNextUrl(null);
        setPrevUrl(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, pageSize, cursor, refreshTick]);

  const goNext = useCallback(() => {
    if (!nextUrl) return;
    prevCursorsRef.current.push(cursor);
    setCursor(nextUrl);
    setExpandedId(null);
  }, [nextUrl, cursor]);

  const goPrev = useCallback(() => {
    const stack = prevCursorsRef.current;
    if (stack.length === 0) {
      // Fallback to server-provided previous cursor.
      if (prevUrl) {
        setCursor(prevUrl);
        setExpandedId(null);
      }
      return;
    }
    const popped = stack.pop() ?? null;
    setCursor(popped);
    setExpandedId(null);
  }, [prevUrl]);

  const applyFilters = useCallback((next: FilterParams) => {
    setFilters(next);
    setCursor(null);
    prevCursorsRef.current = [];
    setExpandedId(null);
    writeUrlFilters(next);
  }, []);

  const resetFilters = useCallback(() => {
    const fresh: FilterParams = { ...defaultDateRange() };
    setFilters(fresh);
    setCursor(null);
    prevCursorsRef.current = [];
    setExpandedId(null);
    writeUrlFilters({});
  }, []);

  const changePageSize = useCallback((n: number) => {
    setPageSize(n);
    setCursor(null);
    prevCursorsRef.current = [];
    setExpandedId(null);
  }, []);

  const refetch = useCallback(() => {
    setRefreshTick((t) => t + 1);
  }, []);

  const hasNext = Boolean(nextUrl);
  const hasPrev = prevCursorsRef.current.length > 0 || Boolean(prevUrl);

  return {
    rows,
    loading,
    error,
    filters,
    pageSize,
    hasNext,
    hasPrev,
    goNext,
    goPrev,
    applyFilters,
    resetFilters,
    changePageSize,
    refetch,
    expandedId,
    setExpandedId,
  };
}
