/**
 * ProgressModal — poll fallback tests (27-02 / SYNC-REL-01 / D-02)
 *
 * Tests the snapshot-poll behaviour added alongside the existing WebSocket:
 *  - Polls on interval while open + non-terminal
 *  - Forward-only merge by last_update_at
 *  - Stops on terminal status (success/failed)
 *  - Stops on modal close / unmount
 *  - WebSocket is still created (poll is additive, not a replacement)
 *  - 404 / null response is tolerated without crashing or overwriting state
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ProgressModal } from "./ProgressModal";
import * as api from "./api";

// jsdom does not implement WebSocket — provide a minimal stub so the WS
// useEffect doesn't throw and we can assert that it was called.
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  close() {
    /* no-op */
  }
}

const SHOP_ID = 42;
const SHOP_NAME = "Test Shop";

const baseSnapshot = {
  shop_id: SHOP_ID,
  status: "fetching" as const,
  step: "fetching" as const,
  fetched: 10,
  total_estimate: 100,
  enriched: 0,
  started_at: "2026-01-01T00:00:00.000Z",
  last_update_at: "2026-01-01T00:00:10.000Z",
  page_count: 1,
};

function makeNewerSnapshot(overrides: Partial<typeof baseSnapshot> = {}) {
  return {
    ...baseSnapshot,
    last_update_at: "2026-01-01T00:00:20.000Z", // 10s later
    ...overrides,
  };
}

function makeOlderSnapshot() {
  return {
    ...baseSnapshot,
    last_update_at: "2026-01-01T00:00:05.000Z", // 5s earlier
    fetched: 5,
  };
}

const defaultProps = {
  open: true,
  shopId: SHOP_ID,
  shopName: SHOP_NAME,
  onClose: vi.fn(),
};

beforeEach(() => {
  vi.useFakeTimers();
  // Reset WebSocket mock
  MockWebSocket.instances = [];
  // @ts-expect-error replacing global for test
  global.WebSocket = MockWebSocket;
  // Default: fetchSyncProgress resolves to null (no snapshot)
  vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Helper: advance fake timers by N intervals and flush microtasks each time
// ---------------------------------------------------------------------------
async function advanceIntervals(count: number, intervalMs = 4_000) {
  for (let i = 0; i < count; i++) {
    await act(async () => {
      vi.advanceTimersByTime(intervalMs);
      // flush promises queued by async callbacks inside setInterval
      await Promise.resolve();
      await Promise.resolve();
    });
  }
}

// ---------------------------------------------------------------------------
// Test 1: Polls on interval while open and non-terminal
// ---------------------------------------------------------------------------
describe("poll fallback — interval polling", () => {
  it("calls fetchSyncProgress at least twice over two poll intervals while open and non-terminal", async () => {
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);

    render(<ProgressModal {...defaultProps} />);

    await advanceIntervals(2);

    expect(api.fetchSyncProgress).toHaveBeenCalledTimes(2);
    expect(api.fetchSyncProgress).toHaveBeenCalledWith(SHOP_ID);
  });
});

// ---------------------------------------------------------------------------
// Test 2: Forward-only merge — newer poll advances state; older poll is ignored
// ---------------------------------------------------------------------------
describe("poll fallback — forward-only merge by last_update_at", () => {
  it("advances snapshot when poll response has a newer last_update_at", async () => {
    const newerPoll = makeNewerSnapshot({ fetched: 50, total_estimate: 200 });
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(newerPoll as Record<string, unknown>);

    render(<ProgressModal {...defaultProps} />);
    await advanceIntervals(1);

    // The modal should now reflect the newer poll data — "50 of ~200" appears
    expect(screen.getByText(/of ~200/)).toBeInTheDocument();
  });

  it("ignores poll response when its last_update_at is older than current snapshot (stale poll)", async () => {
    // Start with a snapshot that the WS would have applied (newer)
    // We'll give a newer poll first to set state, then an older poll should be ignored.
    const newerPoll = makeNewerSnapshot({ fetched: 80, total_estimate: 500 });
    const stalePoll = { ...makeOlderSnapshot(), fetched: 5, total_estimate: 500 }; // older timestamp

    // First interval: apply the newer snapshot
    vi.spyOn(api, "fetchSyncProgress")
      .mockResolvedValueOnce(newerPoll as Record<string, unknown>)
      // Second interval: return a stale snapshot
      .mockResolvedValueOnce(stalePoll as Record<string, unknown>);

    render(<ProgressModal {...defaultProps} />);

    // First poll: applies newer (80 fetched of 500)
    await advanceIntervals(1);
    expect(screen.getByText(/of ~500/)).toBeInTheDocument();

    // Second poll: stale response — state must NOT regress (5 fetched should NOT appear)
    await advanceIntervals(1);
    // "of ~500" should still be showing with 80, not 5
    expect(screen.getByText(/of ~500/)).toBeInTheDocument();
    // The text "5 of ~500" should not appear
    const progressDiv = screen.getByText(/of ~500/);
    expect(progressDiv.textContent).toContain("80");
    expect(progressDiv.textContent).not.toMatch(/^5/);
  });
});

// ---------------------------------------------------------------------------
// Test 3: Stops on terminal status (success)
// ---------------------------------------------------------------------------
describe("poll fallback — stops on terminal status", () => {
  it("stops polling after a success snapshot is applied (no further calls)", async () => {
    const successPoll = {
      ...baseSnapshot,
      status: "success" as const,
      step: "success" as const,
      last_update_at: "2026-01-01T00:01:00.000Z",
    };

    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(
      successPoll as Record<string, unknown>,
    );

    render(<ProgressModal {...defaultProps} />);

    // First interval → applies success snapshot → status becomes "success"
    await advanceIntervals(1);
    const callsAfterFirstInterval = (api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length;

    // Advance two more intervals — the poll should have stopped
    await advanceIntervals(2);
    expect((api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callsAfterFirstInterval,
    );
  });

  it("stops polling after a failed snapshot is applied", async () => {
    const failedPoll = {
      ...baseSnapshot,
      status: "failed" as const,
      step: "failed" as const,
      last_update_at: "2026-01-01T00:01:00.000Z",
    };

    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(
      failedPoll as Record<string, unknown>,
    );

    render(<ProgressModal {...defaultProps} />);

    await advanceIntervals(1);
    const callsAfterFirstInterval = (api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length;

    await advanceIntervals(2);
    expect((api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callsAfterFirstInterval,
    );
  });
});

// ---------------------------------------------------------------------------
// Test 4: Stops on close / unmount
// ---------------------------------------------------------------------------
describe("poll fallback — stops on modal close", () => {
  it("clears the interval when open flips to false (no calls after close)", async () => {
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);

    const { rerender } = render(<ProgressModal {...defaultProps} open={true} />);

    // Advance one interval while open
    await advanceIntervals(1);
    const callsWhileOpen = (api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(callsWhileOpen).toBeGreaterThanOrEqual(1);

    // Close the modal
    rerender(<ProgressModal {...defaultProps} open={false} />);

    // Advance further — no additional calls expected
    await advanceIntervals(2);
    expect((api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callsWhileOpen,
    );
  });

  it("clears the interval when the component unmounts", async () => {
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);

    const { unmount } = render(<ProgressModal {...defaultProps} />);

    await advanceIntervals(1);
    const callsBeforeUnmount = (api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length;

    unmount();

    await advanceIntervals(2);
    expect((api.fetchSyncProgress as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callsBeforeUnmount,
    );
  });
});

// ---------------------------------------------------------------------------
// Test 5: WebSocket is still created (poll is additive — WS not removed)
// ---------------------------------------------------------------------------
describe("WebSocket preserved", () => {
  it("creates a WebSocket connection when the modal opens (poll is additive, not a replacement)", async () => {
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);

    render(<ProgressModal {...defaultProps} />);

    // A WebSocket should have been instantiated
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(1);
    expect(MockWebSocket.instances[0].url).toContain(`/ws/sync-progress/${SHOP_ID}/`);
  });
});

// ---------------------------------------------------------------------------
// Test 6: 404 / null poll response tolerated (no crash, no overwrite)
// ---------------------------------------------------------------------------
describe("poll fallback — 404 / null response tolerated", () => {
  it("does not crash and does not overwrite state when fetchSyncProgress returns null (404)", async () => {
    // First poll applies a snapshot so we have something in state to protect
    const existingPoll = makeNewerSnapshot({ fetched: 25, total_estimate: 999 });
    vi.spyOn(api, "fetchSyncProgress")
      .mockResolvedValueOnce(existingPoll as Record<string, unknown>)
      // Subsequent polls return null (simulating 404)
      .mockResolvedValue(null);

    render(<ProgressModal {...defaultProps} />);

    // First interval sets state ("25 of ~999")
    await advanceIntervals(1);
    expect(screen.getByText(/of ~999/)).toBeInTheDocument();

    // Second interval → null → should not crash and state should be preserved
    await advanceIntervals(1);
    expect(screen.getByText(/of ~999/)).toBeInTheDocument();
  });

  it("does not crash when fetchSyncProgress returns null and there is no existing snapshot", async () => {
    vi.spyOn(api, "fetchSyncProgress").mockResolvedValue(null);

    // Should not throw
    expect(() => render(<ProgressModal {...defaultProps} />)).not.toThrow();
    await advanceIntervals(1);
    // Modal renders in some initial state without crashing
    expect(screen.getByText(/Syncing Test Shop Reviews/)).toBeInTheDocument();
  });
});
