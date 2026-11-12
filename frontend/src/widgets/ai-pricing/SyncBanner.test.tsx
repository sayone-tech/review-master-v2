import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SyncBanner } from "./SyncBanner";
import { syncStatus } from "./syncFixtures";
import * as api from "./api";
import { ApiError } from "./api";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  fetchSyncStatus: vi.fn(),
  toggleSync: vi.fn(),
  triggerSync: vi.fn(),
}));

const ON = { enabled: true, last_status: "success" as const, last_success_at: "2026-11-10T09:00:03Z" };

describe("SyncBanner", () => {
  beforeEach(() => {
    vi.mocked(api.fetchSyncStatus).mockReset();
    vi.mocked(api.toggleSync).mockReset();
    vi.mocked(api.triggerSync).mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("off state shows its badge, copy and Turn on", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByText("Prices change only when you add them.")).toBeInTheDocument();
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Turn on automatic pricing sync" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeInTheDocument();
  });

  it("on state shows the badge, UTC last-synced and next-run times, and Turn off", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ ...ON, next_run_at: "2026-11-16T09:00:00Z" }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(
      await screen.findByText(
        "Last synced Nov 10, 2026 at 09:00 UTC. Next sync Nov 16, 2026 at 09:00 UTC.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("On")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Turn off automatic pricing sync" })).toBeInTheDocument();
  });

  it("on but never synced says so", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus({ enabled: true }));
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByText(/Not synced yet\./)).toBeInTheDocument();
  });

  it("failed state shows the date and View details opens last_error and run time", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({
        enabled: true,
        last_status: "failed",
        last_error: "fetch failed: timeout",
        last_run_at: "2026-11-12T09:00:03Z",
        overdue: true,
      }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByTestId("sync-status-text")).toHaveTextContent("Last sync failed Nov 12, 2026.");
    expect(screen.getByText("Failed")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View details" }));
    expect(screen.getByText("fetch failed: timeout")).toBeInTheDocument();
    expect(screen.getByText(/Nov 12, 2026 at 09:00 UTC/)).toBeInTheDocument();
  });

  it("a fresh running sync shows a neutral in-progress state and keeps Sync Now", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ enabled: true, overdue: true, last_status: "running", last_run_at: "2026-11-12T09:00:03Z" }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByText("Sync in progress…")).toBeInTheDocument();
    expect(screen.getByText("Syncing")).toBeInTheDocument();
    expect(screen.queryByText("Overdue")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View details" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Turn off automatic pricing sync" })).toBeInTheDocument();
  });

  it("details modal lists models skipped because of a concurrent price change", async () => {
    const base = syncStatus().summary;
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({
        enabled: true,
        last_status: "failed",
        last_error: "boom",
        summary: { ...base, skipped_concurrent: ["m-a", "m-b"] },
      }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "View details" }));
    const line = screen.getByTestId("sync-skipped-concurrent");
    expect(line).toHaveTextContent("Skipped because the price changed at the same time: m-a, m-b. The next sync will retry.");
  });

  it("overdue without failure shows the 14-day copy and 'No error recorded.'", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ enabled: true, overdue: true, last_status: "success", last_success_at: "2026-10-01T09:00:00Z" }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByTestId("sync-status-text")).toHaveTextContent(
      "No successful sync in over 14 days.",
    );
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View details" }));
    expect(screen.getByText("No error recorded.")).toBeInTheDocument();
  });

  it("enable asks for confirmation, then toggles, updates and notifies", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.toggleSync).mockResolvedValue(syncStatus(ON));
    const onChanged = vi.fn();
    render(<SyncBanner onChanged={onChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: "Turn on automatic pricing sync" }));
    expect(api.toggleSync).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        "Turn on automatic pricing sync? Prices for models you use will update every Monday 09:00 UTC. Hand-set prices are never changed.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    await vi.waitFor(() => expect(api.toggleSync).toHaveBeenCalledWith(true));
    expect(await screen.findByRole("button", { name: "Turn off automatic pricing sync" })).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("disable confirms with its own copy and cancelling does nothing", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus(ON));
    vi.mocked(api.toggleSync).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Turn off automatic pricing sync" }));
    expect(screen.getByText("Turn off automatic pricing sync?")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("confirm-cancel"));
    expect(api.toggleSync).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Turn off automatic pricing sync" }));
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    await vi.waitFor(() => expect(api.toggleSync).toHaveBeenCalledWith(false));
  });

  it("Sync Now: 202 shows the message and polls every 10 s until the run settles, then calls onChanged", async () => {
    const running = syncStatus({ last_status: "running", last_run_at: "2026-11-12T09:00:00Z" });
    const done = syncStatus({
      last_status: "success",
      last_run_at: "2026-11-12T09:00:00Z",
      last_success_at: "2026-11-12T09:00:05Z",
    });
    vi.mocked(api.fetchSyncStatus).mockResolvedValueOnce(syncStatus());
    vi.mocked(api.fetchSyncStatus).mockResolvedValueOnce(running);
    vi.mocked(api.fetchSyncStatus).mockResolvedValueOnce(running);
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(done);
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onChanged = vi.fn();
    render(<SyncBanner onChanged={onChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    expect(await screen.findByText("Sync started. Refresh in a minute to see results.")).toBeInTheDocument();
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(2);
    expect(onChanged).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(4);
    expect(onChanged).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(4); // polling stopped
  });

  it("polling gives up after 2 minutes if the run never settles", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ last_status: "running", last_run_at: "2026-11-12T09:00:00Z" }),
    );
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onChanged = vi.fn();
    render(<SyncBanner onChanged={onChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300_000);
    });
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(13); // initial + 12 polls
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("a second Sync Now click restarts the poller instead of running two", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ last_status: "running", last_run_at: "2026-11-12T09:00:00Z" }),
    );
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    await userEvent.click(screen.getByRole("button", { name: "Sync now" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    // initial load + exactly one poll in the 10 s after the restart (not two pollers).
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(2);
  });

  it("clears the poller on unmount", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { unmount } = render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await screen.findByText(/Sync started/);
    unmount();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(1);
  });

  it("reloads the status when refreshKey changes", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    const { rerender } = render(<SyncBanner onChanged={vi.fn()} refreshKey={0} />);
    await screen.findByTestId("sync-banner");
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(1);
    rerender(<SyncBanner onChanged={vi.fn()} refreshKey={1} />);
    await vi.waitFor(() => expect(api.fetchSyncStatus).toHaveBeenCalledTimes(2));
  });

  it("an enabled, never-run, not-overdue status shows On and Not synced yet", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus({ enabled: true, overdue: false }));
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByText("Not synced yet.")).toBeInTheDocument();
    expect(screen.getByText("On")).toBeInTheDocument();
  });

  it("Sync Now 429 shows the rate-limit message", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.triggerSync).mockRejectedValue(new ApiError(429, "Request was throttled."));
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    expect(await screen.findByText("Sync now can be used once every 15 minutes.")).toBeInTheDocument();
  });

  it("lists skipped hand-set prices and 'Use LiteLLM price' passes the LiteLLM values", async () => {
    const skipped = {
      model: "m3",
      ours: { input: "0.15000000", output: "0.60000000", cached: "0.07500000" },
      litellm: { input: "0.10000000", output: "0.40000000", cached: "0.05000000" },
    };
    const base = syncStatus(ON);
    vi.mocked(api.fetchSyncStatus).mockResolvedValue({
      ...base,
      summary: { ...base.summary, skipped_manual: [skipped] },
    });
    const onUse = vi.fn();
    render(<SyncBanner onChanged={vi.fn()} onUseLiteLLM={onUse} />);
    expect(await screen.findByText(/1 hand-set price differs from LiteLLM\./)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Use LiteLLM price" })).not.toBeInTheDocument();
    const review = screen.getByRole("button", { name: "Review" });
    await userEvent.click(review);
    expect(review).toHaveAttribute("aria-expanded", "true");
    const row = screen.getByRole("row", { name: /m3/ });
    expect(row).toHaveTextContent(
      "$0.150000 / $0.600000 / $0.075000$0.100000 / $0.400000 / $0.050000",
    );
    await userEvent.click(screen.getByRole("button", { name: "Use LiteLLM price" }));
    expect(onUse).toHaveBeenCalledWith("m3", skipped.litellm);
  });

  it("shows an error with Retry when status fails to load", async () => {
    vi.mocked(api.fetchSyncStatus).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Prices change only when you add them.")).toBeInTheDocument();
  });

  it("shows a failed run even when sync is off, keeps Turn on and opens details", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({
        enabled: false,
        last_status: "failed",
        last_error: "fetch failed: timeout",
        last_run_at: "2026-11-12T09:00:03Z",
      }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByTestId("sync-status-text")).toHaveTextContent("Last sync failed Nov 12, 2026.");
    await userEvent.click(screen.getByRole("button", { name: "View details" }));
    expect(screen.getByText("fetch failed: timeout")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Turn on automatic pricing sync" })).toBeInTheDocument();
  });

  it("a disabled sync's Sync now that fails shows the Failed state after the first poll", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValueOnce(syncStatus());
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ last_status: "failed", last_error: "boom", last_run_at: "2026-11-12T09:00:03Z" }),
    );
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await screen.findByText(/Sync started/);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(screen.getByTestId("sync-status-text")).toHaveTextContent("Last sync failed Nov 12, 2026.");
    expect(screen.getByRole("button", { name: "View details" })).toBeInTheDocument();
  });
});
