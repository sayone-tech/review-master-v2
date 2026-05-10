import { useCallback, useState } from "react";
import { createTarget, deleteTarget, listTargets, patchTarget } from "./targetsApi";
import type { TargetCreatePayload, TargetRow, TargetUpdatePayload } from "./types";

interface UseTargetsState {
  rows: TargetRow[];
  loading: boolean;
  error: string | null;
}

export function useTargets(shopId: number | null) {
  const [state, setState] = useState<UseTargetsState>({
    rows: [],
    loading: false,
    error: null,
  });

  const load = useCallback(async () => {
    if (shopId === null) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const rows = await listTargets(shopId);
      setState({ rows, loading: false, error: null });
    } catch {
      setState((s) => ({ ...s, loading: false, error: "Failed to load targets." }));
    }
  }, [shopId]);

  const addTarget = useCallback(
    async (payload: TargetCreatePayload): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        await createTarget(shopId, payload);
        // Re-fetch for correct ordering from server
        const rows = await listTargets(shopId);
        setState((s) => ({ ...s, rows }));
        return null;
      } catch (err: unknown) {
        if (err && typeof err === "object" && "data" in err) {
          const data = (err as { data: unknown }).data;
          if (data && typeof data === "object" && "non_field_errors" in data) {
            const nfe = (data as { non_field_errors: string[] }).non_field_errors;
            return nfe[0] ?? "Failed to save target.";
          }
        }
        return "Failed to save target.";
      }
    },
    [shopId],
  );

  const editTarget = useCallback(
    async (targetId: number, payload: TargetUpdatePayload): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        const updated = await patchTarget(shopId, targetId, payload);
        setState((s) => ({
          ...s,
          rows: s.rows.map((r) => (r.id === targetId ? updated : r)),
        }));
        return null;
      } catch {
        return "Failed to update target.";
      }
    },
    [shopId],
  );

  const removeTarget = useCallback(
    async (targetId: number): Promise<string | null> => {
      if (shopId === null) return "No shop selected.";
      try {
        await deleteTarget(shopId, targetId);
        setState((s) => ({ ...s, rows: s.rows.filter((r) => r.id !== targetId) }));
        return null;
      } catch {
        return "Failed to delete target.";
      }
    },
    [shopId],
  );

  return {
    rows: state.rows,
    loading: state.loading,
    error: state.error,
    load,
    addTarget,
    editTarget,
    removeTarget,
  };
}
