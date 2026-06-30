// Phase 25-03 — Poll hook for merge job progress.
// Clones useNotifications.ts: setInterval/clearInterval pattern.
// 2s interval, auto-stops on terminal status (SUCCESS/FAILED).

import { useCallback, useEffect, useState } from "react";
import { dismissMergeJob, fetchActiveJob } from "./api";
import type { TagMergeJobRow } from "./types";

export function useMergeProgress() {
  const [job, setJob] = useState<TagMergeJobRow | null>(null);
  // Local session dismissed state — hides banner for current view without deleting job
  const [dismissed, setDismissed] = useState(false);

  const fetchJob = useCallback(async () => {
    try {
      const data = await fetchActiveJob();
      setJob(data);
      // If a new job appears, reset dismissed state
      if (data) setDismissed(false);
    } catch {
      // Best-effort — silently swallow transient errors
    }
  }, []);

  // Poll while PENDING/IN_PROGRESS; auto-stop on SUCCESS/FAILED (mirrors useNotifications)
  useEffect(() => {
    void fetchJob();
    if (job?.status === "PENDING" || job?.status === "IN_PROGRESS") {
      const id = setInterval(() => void fetchJob(), 2_000);
      return () => clearInterval(id);
    }
  }, [job?.status, fetchJob]);

  const dismiss = async () => {
    if (!job) return;
    if (job.status === "FAILED") {
      // FAILED: PATCH the job to dismissed so it won't re-appear on reload
      try {
        await dismissMergeJob(job.id);
      } catch {
        // best-effort
      }
      setJob(null);
    } else {
      // IN_PROGRESS / PENDING: local session hide only
      setDismissed(true);
    }
  };

  const kickoff = () => {
    // Called right after a merge starts — begin polling immediately
    setDismissed(false);
    void fetchJob();
  };

  const visible = job !== null && !dismissed;

  return { job, visible, dismiss, kickoff, refetch: fetchJob };
}
