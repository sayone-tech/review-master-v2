import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ReplyComposer } from "./ReplyComposer";
import type { ReviewRow } from "./types";
import * as api from "./api";
import * as templatesApi from "../reply-templates/api";
import { resetCreditsStoreForTests } from "../credits/creditsStore";

function fakeRow(over: Partial<ReviewRow> = {}): ReviewRow {
  return {
    id: 1,
    shop_id: 7,
    shop_name: "Downtown",
    shop_region_name: "North",
    region_id: 1,
    google_review_id: "g1",
    star_rating: 5,
    reviewer_display_name: "Sam",
    reviewer_photo_url: "",
    reviewer_is_anonymous: false,
    comment: "Great coffee",
    review_create_time: "2026-04-01T00:00:00Z",
    review_update_time: "2026-04-01T00:00:00Z",
    reply_comment: "",
    reply_update_time: null,
    is_replied: false,
    replied_by_name: null,
    enrichment_status: "SUCCESS",
    sentiment: "positive",
    tags: [],
    extracted_action_items: [],
    has_action_items: false,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
    ...over,
  };
}

function renderComposer(row: ReviewRow = fakeRow()) {
  return render(
    <table>
      <tbody>
        <ReplyComposer
          row={row}
          totalColumns={5}
          showFullComment={false}
          onToggleShowFullComment={() => {}}
          onSuccess={() => {}}
          onClose={() => {}}
        />
      </tbody>
    </table>,
  );
}

let costSpy: MockInstance<typeof api.getCreditCost>;
let generateSpy: MockInstance<typeof api.generateReply>;

beforeEach(() => {
  resetCreditsStoreForTests();
  costSpy = vi
    .spyOn(api, "getCreditCost")
    .mockResolvedValue({ cost: 2, remaining: 35, is_enabled: true });
  generateSpy = vi
    .spyOn(api, "generateReply")
    .mockResolvedValue({ draft: "Thanks!", credits_charged: 2, credits_remaining: 33 });
  vi.spyOn(templatesApi, "listTemplates").mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReplyComposer credit awareness (tracer, CVIS-03)", () => {
  it("shows the server cost and remaining credits and updates the line after a generate", async () => {
    renderComposer();

    const button = await screen.findByRole("button", { name: "Generate with AI · 2 credits" });
    expect(button).toHaveTextContent("Generate with AI · 2 credits");
    expect(await screen.findByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
    expect(costSpy).toHaveBeenCalledWith(1, expect.any(AbortSignal));

    fireEvent.click(button);
    fireEvent.click(screen.getByRole("button", { name: /Generate Professional reply/ }));

    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Write your reply" })).toHaveValue("Thanks!"),
    );
    expect(generateSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText("This shop has 33 credits remaining this month.")).toBeInTheDocument();
  });
});
