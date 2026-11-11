import { describe, it, expect, vi, beforeEach, afterEach, type MockInstance } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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

function mountContact(): void {
  const el = document.createElement("script");
  el.id = "credit-contact";
  el.type = "application/json";
  el.textContent = JSON.stringify({
    organisation_name: "Acme Foods",
    support_email: "support@reviewbee.in",
  });
  document.body.appendChild(el);
}

beforeEach(() => {
  mountContact();
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
  document.getElementById("credit-contact")?.remove();
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

describe("ReplyComposer credit states (CVIS-03, D-06, D-07)", () => {
  it("renders no AI button, credit line or cost request when the review is star-only", async () => {
    renderComposer(fakeRow({ comment: "   " }));
    await act(async () => {});
    expect(screen.queryByRole("button", { name: /Generate with AI/ })).not.toBeInTheDocument();
    expect(document.getElementById("credit-status-1")).toBeNull();
    expect(screen.queryByText("Buy More Credits")).not.toBeInTheDocument();
    expect(costSpy).not.toHaveBeenCalled();
  });

  it("disables the button with aria-busy and shows Checking credits while the cost is pending", async () => {
    costSpy.mockReturnValue(new Promise(() => {}));
    renderComposer();
    await act(async () => {});
    const button = screen.getByRole("button", { name: "Generate with AI" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Checking credits…")).toBeInTheDocument();
  });

  it("disables the button without a cost and without Buy More when AI is not enabled", async () => {
    costSpy.mockResolvedValue({ cost: 2, remaining: 0, is_enabled: false });
    renderComposer();
    expect(await screen.findByText("AI replies aren't enabled for this shop.")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Generate with AI" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "credit-status-1");
    expect(screen.queryByTestId("credit-buy-more-1")).not.toBeInTheDocument();
    expect(button).not.toHaveAttribute("title");
  });

  it("shows the shortfall and opens the Buy More modal without review text when credits are insufficient", async () => {
    costSpy.mockResolvedValue({ cost: 3, remaining: 1, is_enabled: true });
    renderComposer(fakeRow({ comment: "SECRET-REVIEW-TEXT" }));
    expect(
      await screen.findByText("Not enough credits — this reply needs 3, you have 1."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate with AI · 3 credits" })).toBeDisabled();

    fireEvent.click(screen.getByTestId("credit-buy-more-1"));
    const dialog = screen.getByRole("dialog", { name: "Buy More Credits" });
    expect(dialog).toBeInTheDocument();
    const href = screen.getByRole("link", { name: "Contact Admin" }).getAttribute("href") as string;
    const query = href.slice(href.indexOf("?") + 1);
    const decoded = query
      .split("&")
      .map((part) => decodeURIComponent(part))
      .join("\n");
    expect(decoded).toContain("Credit request — Acme Foods / Downtown");
    expect(decoded).not.toContain("SECRET-REVIEW-TEXT");
  });

  it("fails open on a load error and recovers through Retry Credit Check", async () => {
    costSpy.mockRejectedValueOnce(new api.ApiError(500, null));
    renderComposer();
    expect(await screen.findByText("Couldn't check your credit balance.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate with AI" })).toBeEnabled();

    fireEvent.click(screen.getByTestId("credit-retry-1"));
    expect(await screen.findByRole("button", { name: "Generate with AI · 2 credits" })).toBeEnabled();
    expect(costSpy).toHaveBeenCalledTimes(2);
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });

  it("shows plain tone pills without a draft and cost pills once a draft exists", async () => {
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI · 2 credits" }));
    expect(screen.getByRole("button", { name: "Generate Professional reply" })).toHaveTextContent(
      /^Professional$/,
    );
    expect(screen.getByRole("button", { name: "Generate Friendly reply" })).toHaveTextContent(/^Friendly$/);

    fireEvent.change(screen.getByRole("textbox", { name: "Write your reply" }), {
      target: { value: "My draft" },
    });
    const pro = screen.getByRole("button", { name: "Generate Professional reply, 2 credits" });
    expect(pro).toHaveTextContent("Professional · 2 cr");
    expect(screen.getByRole("button", { name: "Generate Friendly reply, 2 credits" })).toHaveTextContent(
      "Friendly · 2 cr",
    );
  });

  it("uses the singular credit in the pill label when the cost is 1", async () => {
    costSpy.mockResolvedValue({ cost: 1, remaining: 10, is_enabled: true });
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI · 1 credit" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Write your reply" }), {
      target: { value: "My draft" },
    });
    expect(screen.getByRole("button", { name: "Generate Professional reply, 1 credit" })).toBeInTheDocument();
  });

  it("disables every tone pill while a generate is pending", async () => {
    generateSpy.mockReturnValue(new Promise(() => {}));
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI · 2 credits" }));
    fireEvent.click(screen.getByRole("button", { name: "Generate Professional reply" }));
    expect(screen.getByRole("button", { name: "Generating Professional reply…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate Friendly reply" })).toBeDisabled();
  });

  it("never derives a cost on the client when the server supplies none", async () => {
    costSpy.mockRejectedValue(new api.ApiError(500, null));
    renderComposer(fakeRow({ comment: "x".repeat(900) }));
    expect(await screen.findByText("Couldn't check your credit balance.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate with AI" })).toBeInTheDocument();
  });
});
