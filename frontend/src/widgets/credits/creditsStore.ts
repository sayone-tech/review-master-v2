import { useSyncExternalStore } from "react";

/**
 * Module-level balance store keyed by shop_id. The Shops page renders separate
 * React roots (table + modals) that must share one balance, so this is a plain
 * module store read through useSyncExternalStore, not React context.
 */
export interface ShopCreditsEntry {
  remaining: number;
  total?: number;
  isEnabled: boolean;
  periodLabel?: string;
}

export interface ShopCreditsUpdate {
  remaining: number | null | undefined;
  total?: number | null;
  isEnabled?: boolean;
  periodLabel?: string | null;
}

const entries = new Map<number, ShopCreditsEntry>();
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of Array.from(listeners)) listener();
}

/**
 * Merge an update for one shop. A non-finite `remaining` (null from a 200/422/
 * 502 response, NaN, undefined) is ignored entirely so a known balance is never
 * blanked. Omitted/null total and periodLabel keep the previous values.
 */
export function setShopCredits(shopId: number, update: ShopCreditsUpdate): void {
  const { remaining } = update;
  if (typeof remaining !== "number" || !Number.isFinite(remaining)) return;

  const previous = entries.get(shopId);
  const next: ShopCreditsEntry = {
    remaining,
    total: update.total ?? previous?.total,
    isEnabled: update.isEnabled ?? previous?.isEnabled ?? true,
    periodLabel: update.periodLabel ?? previous?.periodLabel,
  };
  entries.set(shopId, next);
  notify();
}

export function getShopCredits(shopId: number): ShopCreditsEntry | undefined {
  return entries.get(shopId);
}

export function subscribeShopCredits(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useShopCredits(shopId: number): ShopCreditsEntry | undefined {
  return useSyncExternalStore(subscribeShopCredits, () => getShopCredits(shopId));
}

export function resetCreditsStoreForTests(): void {
  entries.clear();
}
