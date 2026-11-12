import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyncCaveat, syncStatusWord } from "./SyncCaveat";
import { syncStatus } from "../ai-pricing/syncFixtures";
import * as api from "../ai-pricing/api";

vi.mock("../ai-pricing/api", async (orig) => ({
  ...(await orig<typeof import("../ai-pricing/api")>()),
  fetchSyncStatus: vi.fn(),
}));

const NOW = new Date("2026-11-12T10:00:00Z");
const ok = (iso: string) => syncStatus({ enabled: true, last_status: "success", last_success_at: iso });

describe("syncStatusWord", () => {
  it("covers every state", () => {
    expect(syncStatusWord(ok("2026-11-12T00:01:00Z"), NOW)).toBe("synced today");
    expect(syncStatusWord(ok("2026-11-11T23:59:00Z"), NOW)).toBe("synced 1 day ago");
    expect(syncStatusWord(ok("2026-11-07T09:00:00Z"), NOW)).toBe("synced 5 days ago");
    expect(syncStatusWord(syncStatus({ enabled: false }), NOW)).toBe("sync off");
    expect(
      syncStatusWord(syncStatus({ enabled: true, last_status: "failed", last_success_at: "2026-11-12T01:00:00Z" }), NOW),
    ).toBe("sync failed");
    expect(syncStatusWord(syncStatus({ enabled: true }), NOW)).toBe("not synced yet");
    expect(syncStatusWord(syncStatus({ enabled: false, last_status: "failed" }), NOW)).toBe("sync failed");
    expect(syncStatusWord(syncStatus({ enabled: true, last_status: "running" }), NOW)).toBe("sync in progress");
    expect(syncStatusWord(syncStatus({ enabled: false, last_status: "running" }), NOW)).toBe("sync in progress");
  });
});

describe("SyncCaveat", () => {
  beforeEach(() => {
    vi.mocked(api.fetchSyncStatus).mockReset();
  });

  it("renders the sync-aware footer", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    render(<p data-testid="f"><SyncCaveat /></p>);
    expect(
      await screen.findByText(
        "Based on configured pricing; sync status: sync off. Actual OpenAI invoice is authoritative.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the Phase 34 caveat when the status request fails", async () => {
    vi.mocked(api.fetchSyncStatus).mockImplementation(() => Promise.reject(new Error("403")));
    render(<p><SyncCaveat /></p>);
    await vi.waitFor(() => expect(api.fetchSyncStatus).toHaveBeenCalled());
    expect(
      screen.getByText("Estimated based on configured pricing — actual OpenAI invoice is authoritative."),
    ).toBeInTheDocument();
  });
});
