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

  it("off state shows its copy and Enable sync", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(
      await screen.findByText("Automatic pricing sync is off. Prices update only when you add them manually."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable sync" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync Now" })).toBeInTheDocument();
  });

  it("on state shows the UTC last-synced time and Disable sync", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus(ON));
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(
      await screen.findByText("Automatic pricing sync is on. Last synced: Nov 10, 2026 at 09:00 UTC."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable sync" })).toBeInTheDocument();
  });

  it("on but never synced says so", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus({ enabled: true }));
    render(<SyncBanner onChanged={vi.fn()} />);
    expect(await screen.findByText(/Not synced yet\./)).toBeInTheDocument();
  });

  it("failed state is clickable and the modal shows last_error and run time", async () => {
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
    await userEvent.click(await screen.findByRole("button", { name: "Last sync failed Nov 12, 2026. Click to view details." }));
    expect(screen.getByText("fetch failed: timeout")).toBeInTheDocument();
    expect(screen.getByText(/Nov 12, 2026 at 09:00 UTC/)).toBeInTheDocument();
  });

  it("overdue without failure shows the 14-day copy and 'No error recorded.'", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ enabled: true, overdue: true, last_status: "success", last_success_at: "2026-10-01T09:00:00Z" }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "No successful sync in over 14 days. Click to view details." }),
    );
    expect(screen.getByText("No error recorded.")).toBeInTheDocument();
  });

  it("enable asks for confirmation, then toggles, updates and notifies", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.toggleSync).mockResolvedValue(syncStatus(ON));
    const onChanged = vi.fn();
    render(<SyncBanner onChanged={onChanged} />);
    await userEvent.click(await screen.findByRole("button", { name: "Enable sync" }));
    expect(api.toggleSync).not.toHaveBeenCalled();
    expect(
      screen.getByText(
        "Turn on automatic pricing sync? Prices for models you use will update every Monday 09:00 UTC. Hand-set prices are never changed.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    await vi.waitFor(() => expect(api.toggleSync).toHaveBeenCalledWith(true));
    expect(await screen.findByRole("button", { name: "Disable sync" })).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("disable confirms with its own copy and cancelling does nothing", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus(ON));
    vi.mocked(api.toggleSync).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Disable sync" }));
    expect(screen.getByText("Turn off automatic pricing sync?")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("confirm-cancel"));
    expect(api.toggleSync).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Disable sync" }));
    await userEvent.click(screen.getByTestId("confirm-confirm"));
    await vi.waitFor(() => expect(api.toggleSync).toHaveBeenCalledWith(false));
  });

  it("Sync Now: 202 shows the message and refetches once after 30 s", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync Now" }));
    expect(await screen.findByText("Sync started. Refresh in a minute to see results.")).toBeInTheDocument();
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(2);
  });

  it("clears the pending refetch on unmount", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { unmount } = render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync Now" }));
    await screen.findByText(/Sync started/);
    unmount();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(api.fetchSyncStatus).toHaveBeenCalledTimes(1);
  });

  it("Sync Now 429 shows the rate-limit message", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    vi.mocked(api.triggerSync).mockRejectedValue(new ApiError(429, "Request was throttled."));
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync Now" }));
    expect(await screen.findByText("Sync Now can be used once every 15 minutes.")).toBeInTheDocument();
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
    expect(await screen.findByText("1 hand-set price differs from LiteLLM")).toBeInTheDocument();
    expect(
      screen.getByText(/ours \$0\.150000\/\$0\.600000\/\$0\.075000 · LiteLLM \$0\.100000\/\$0\.400000\/\$0\.050000/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Use LiteLLM price" }));
    expect(onUse).toHaveBeenCalledWith("m3", skipped.litellm);
  });

  it("shows an error with Retry when status fails to load", async () => {
    vi.mocked(api.fetchSyncStatus).mockRejectedValueOnce(new Error("boom"));
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(syncStatus());
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Automatic pricing sync is off/)).toBeInTheDocument();
  });

  it("shows a failed run even when sync is off, keeps Enable sync and opens details", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({
        enabled: false,
        last_status: "failed",
        last_error: "fetch failed: timeout",
        last_run_at: "2026-11-12T09:00:03Z",
      }),
    );
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Last sync failed Nov 12, 2026. Click to view details." }),
    );
    expect(screen.getByText("fetch failed: timeout")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable sync" })).toBeInTheDocument();
  });

  it("a disabled Sync Now that fails turns the banner amber after the 30 s refetch", async () => {
    vi.mocked(api.fetchSyncStatus).mockResolvedValueOnce(syncStatus());
    vi.mocked(api.fetchSyncStatus).mockResolvedValue(
      syncStatus({ last_status: "failed", last_error: "boom", last_run_at: "2026-11-12T09:00:03Z" }),
    );
    vi.mocked(api.triggerSync).mockResolvedValue(undefined);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<SyncBanner onChanged={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync Now" }));
    await screen.findByText(/Sync started/);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(
      await screen.findByRole("button", { name: "Last sync failed Nov 12, 2026. Click to view details." }),
    ).toBeInTheDocument();
  });
});
