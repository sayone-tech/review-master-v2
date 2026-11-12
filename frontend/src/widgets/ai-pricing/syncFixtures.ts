import type { SyncStatus } from "./types";

export function syncStatus(over: Partial<SyncStatus> = {}): SyncStatus {
  return {
    enabled: false,
    last_run_at: null,
    last_success_at: null,
    last_status: "never",
    last_error: "",
    overdue: false,
    next_run_at: null,
    summary: {
      added: [],
      updated: [],
      unchanged: [],
      skipped_manual: [],
      skipped_scheduled: [],
      skipped_concurrent: [],
      unpriced: [],
      errored: [],
    },
    ...over,
  };
}
