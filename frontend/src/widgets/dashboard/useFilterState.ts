import { useCallback, useState } from "react";
import type { DashboardFilters, DateRangePreset } from "./types";

const STORAGE_KEY = "dashboard-filters";

function todayUTC(): string {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
    .toISOString()
    .slice(0, 10);
}

function daysAgoUTC(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))
    .toISOString()
    .slice(0, 10);
}

export function presetToAbsoluteDates(preset: DateRangePreset): {
  date_from: string | null;
  date_to: string | null;
} {
  if (preset === "7d") return { date_from: daysAgoUTC(7), date_to: todayUTC() };
  if (preset === "30d") return { date_from: daysAgoUTC(30), date_to: todayUTC() };
  if (preset === "90d") return { date_from: daysAgoUTC(90), date_to: todayUTC() };
  // "all" and "custom": no computed dates
  return { date_from: null, date_to: null };
}

export const DEFAULT_FILTERS: DashboardFilters = {
  region_id: null,
  shop_id: null,
  range: "all",
  date_from: null,
  date_to: null,
};

function parseFromUrl(url: URLSearchParams): DashboardFilters | null {
  const hasAny = ["region", "store", "range", "from", "to"].some((k) => url.has(k));
  if (!hasAny) return null;
  const range = (url.get("range") ?? "all") as DateRangePreset;
  const region_id = url.get("region") ? Number(url.get("region")) : null;
  const shop_id = url.get("store") ? Number(url.get("store")) : null;
  if (range === "custom") {
    return {
      region_id,
      shop_id,
      range,
      date_from: url.get("from"),
      date_to: url.get("to"),
    };
  }
  return { region_id, shop_id, range, ...presetToAbsoluteDates(range) };
}

function readFromSession(): DashboardFilters | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DashboardFilters) : null;
  } catch {
    return null;
  }
}

function writeToSession(f: DashboardFilters): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(f));
  } catch {
    /* ignore */
  }
}

function syncToUrl(f: DashboardFilters): void {
  const p = new URLSearchParams();
  if (f.region_id) p.set("region", String(f.region_id));
  if (f.shop_id) p.set("store", String(f.shop_id));
  if (f.range !== "all") p.set("range", f.range);
  if (f.range === "custom") {
    if (f.date_from) p.set("from", f.date_from);
    if (f.date_to) p.set("to", f.date_to);
  }
  const qs = p.toString();
  window.history.replaceState({}, "", qs ? `?${qs}` : window.location.pathname);
}

export function isDefault(f: DashboardFilters): boolean {
  return f.region_id === null && f.shop_id === null && f.range === "all";
}

export interface UseFilterStateReturn {
  filters: DashboardFilters;
  setRegion: (id: number | null) => void;
  setStore: (id: number | null) => void;
  setDateRange: (preset: DateRangePreset) => void;
  setCustomRange: (from: string, to: string) => void;
  applyAll: (region_id: number | null, shop_id: number | null, range: DateRangePreset, date_from: string | null, date_to: string | null) => void;
  clearFilters: () => void;
  clearOutOfScope: (kind: "region" | "store") => void;
}

export function useFilterState(): UseFilterStateReturn {
  const [filters, setFilters] = useState<DashboardFilters>(() => {
    // FILT-07: URL params take precedence over sessionStorage
    if (typeof window === "undefined") return DEFAULT_FILTERS;
    const fromUrl = parseFromUrl(new URLSearchParams(window.location.search));
    if (fromUrl) return fromUrl;
    const fromSession = readFromSession();
    return fromSession ?? DEFAULT_FILTERS;
  });

  const update = useCallback((next: DashboardFilters) => {
    setFilters(next);
    syncToUrl(next);
    writeToSession(next);
  }, []);

  const setRegion = useCallback(
    (id: number | null) => {
      update({ ...filters, region_id: id, shop_id: null });
    },
    [filters, update],
  );

  const setStore = useCallback(
    (id: number | null) => {
      update({ ...filters, shop_id: id });
    },
    [filters, update],
  );

  const setDateRange = useCallback(
    (preset: DateRangePreset) => {
      if (preset === "custom") {
        update({ ...filters, range: "custom", date_from: null, date_to: null });
        return;
      }
      update({ ...filters, range: preset, ...presetToAbsoluteDates(preset) });
    },
    [filters, update],
  );

  const setCustomRange = useCallback(
    (from: string, to: string) => {
      update({ ...filters, range: "custom", date_from: from, date_to: to });
    },
    [filters, update],
  );

  const applyAll = useCallback(
    (
      region_id: number | null,
      shop_id: number | null,
      range: DateRangePreset,
      date_from: string | null,
      date_to: string | null,
    ) => {
      const dates =
        range === "custom"
          ? { date_from, date_to }
          : presetToAbsoluteDates(range);
      update({ region_id, shop_id, range, ...dates });
    },
    [update],
  );

  const clearFilters = useCallback(() => {
    update(DEFAULT_FILTERS);
  }, [update]);

  const clearOutOfScope = useCallback(
    (kind: "region" | "store") => {
      if (kind === "region") update({ ...filters, region_id: null, shop_id: null });
      else update({ ...filters, shop_id: null });
    },
    [filters, update],
  );

  return {
    filters,
    setRegion,
    setStore,
    setDateRange,
    setCustomRange,
    applyAll,
    clearFilters,
    clearOutOfScope,
  };
}
