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
    shop_is_active: true,
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

    const button = await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" });
    expect(button).toHaveTextContent("Generate with AI (requires 2 credits)");
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

  it("should show remaining of total under the AI button when the server sends the monthly total", async () => {
    costSpy.mockResolvedValue({ cost: 2, remaining: 18, total: 20, is_enabled: true });
    renderComposer();

    expect(await screen.findByText("18 of 20 credits left this month")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate with AI (requires 2 credits)" })).toBeEnabled();
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
    expect(screen.getByRole("button", { name: "Generate with AI (requires 3 credits)" })).toBeDisabled();

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
    expect(await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" })).toBeEnabled();
    expect(costSpy).toHaveBeenCalledTimes(2);
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });

  it("shows plain tone pills without a draft and cost pills once a draft exists", async () => {
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI (requires 1 credit)" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Write your reply" }), {
      target: { value: "My draft" },
    });
    expect(screen.getByRole("button", { name: "Generate Professional reply, 1 credit" })).toBeInTheDocument();
  });

  it("disables every tone pill while a generate is pending", async () => {
    generateSpy.mockReturnValue(new Promise(() => {}));
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" }));
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

async function openPanelAndGenerate(buttonName: string, toneName: RegExp | string): Promise<void> {
  const button = await screen.findByRole("button", { name: buttonName });
  await act(async () => {}); // flush the templates fetch before interacting
  fireEvent.click(button);
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: toneName }));
  });
}

describe("ReplyComposer generate outcomes (CVIS-03, D-08)", () => {
  it("keeps the draft, closes the panel and switches to insufficient on a 402 exhausted", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(402, { code: "insufficient_credits", reason: "exhausted", required: 3, remaining: 1 }),
    );
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" }));
    const textarea = screen.getByRole("textbox", { name: "Write your reply" });
    fireEvent.change(textarea, { target: { value: "My draft" } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Professional reply/ }));

    expect(
      await screen.findByText("Not enough credits — this reply needs 3, you have 1."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /AI reply/ })).not.toBeInTheDocument();
    expect(textarea).toHaveValue("My draft");
    expect(screen.getByRole("button", { name: "Generate with AI (requires 3 credits)" })).toBeDisabled();
    expect(document.activeElement).toBe(textarea);
  });

  it("switches to not enabled with no Buy More link on a 402 not_enabled and keeps the draft", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(402, { code: "insufficient_credits", reason: "not_enabled", required: 2, remaining: 0 }),
    );
    renderComposer();
    fireEvent.click(await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" }));
    const textarea = screen.getByRole("textbox", { name: "Write your reply" });
    fireEvent.change(textarea, { target: { value: "Keep me" } });
    fireEvent.click(screen.getByRole("button", { name: /Generate Friendly reply/ }));

    expect(await screen.findByText("AI replies aren't enabled for this shop.")).toBeInTheDocument();
    expect(screen.queryByTestId("credit-buy-more-1")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(textarea).toHaveValue("Keep me");
    expect(document.activeElement).toBe(textarea);
  });

  it("recovers a failed cost check into the 402 state using the response numbers", async () => {
    costSpy.mockRejectedValue(new api.ApiError(500, null));
    generateSpy.mockRejectedValue(
      new api.ApiError(402, { code: "insufficient_credits", reason: "exhausted", required: 4, remaining: 0 }),
    );
    renderComposer();
    await screen.findByText("Couldn't check your credit balance.");
    await openPanelAndGenerate("Generate with AI", "Generate Professional reply");
    expect(
      await screen.findByText("Not enough credits — this reply needs 4, you have 0."),
    ).toBeInTheDocument();
  });

  it("shows the in-progress banner on a 409 and leaves the button enabled", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(409, { code: "generation_in_progress", detail: "busy" }),
    );
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A reply is already being generated for this review. Please wait a moment.",
    );
    expect(screen.getByRole("button", { name: "Generate with AI (requires 2 credits)" })).toBeEnabled();
  });

  it("updates the line from a 422 credits_remaining and shows the moderation copy", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(422, {
        code: "content_moderated",
        detail: "Moderated copy.",
        credits_charged: 2,
        credits_remaining: 30,
      }),
    );
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    expect(await screen.findByRole("alert")).toHaveTextContent("Moderated copy.");
    expect(screen.getByText("This shop has 30 credits remaining this month.")).toBeInTheDocument();
  });

  it("keeps the previous remaining when a 502 carries a null credits_remaining", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(502, { code: "ai_unavailable", detail: "x", credits_charged: 0, credits_remaining: null }),
    );
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AI generation failed. Please try again or write your reply manually.",
    );
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });

  it("updates the line from a 502 numeric credits_remaining", async () => {
    generateSpy.mockRejectedValue(
      new api.ApiError(502, { code: "ai_unavailable", detail: "x", credits_charged: 0, credits_remaining: 35 }),
    );
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    await screen.findByRole("alert");
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });

  it("applies the draft and leaves remaining unchanged when a 200 has null credits_remaining", async () => {
    generateSpy.mockResolvedValue({ draft: "Hello", credits_charged: 2, credits_remaining: null });
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Write your reply" })).toHaveValue("Hello"));
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });

  it("switches to insufficient after a success that leaves fewer credits than the cost", async () => {
    generateSpy.mockResolvedValue({ draft: "Hello", credits_charged: 2, credits_remaining: 1 });
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    expect(
      await screen.findByText("Not enough credits — this reply needs 2, you have 1."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate with AI (requires 2 credits)" })).toBeDisabled();
  });

  it("shares remaining between two composers of the same shop while keeping each cost", async () => {
    costSpy.mockImplementation(async (id: number) =>
      id === 1
        ? { cost: 2, remaining: 35, is_enabled: true }
        : { cost: 3, remaining: 35, is_enabled: true },
    );
    generateSpy.mockResolvedValue({ draft: "Hi", credits_charged: 2, credits_remaining: 10 });
    render(
      <table>
        <tbody>
          {[fakeRow({ id: 1 }), fakeRow({ id: 2, google_review_id: "g2" })].map((r) => (
            <ReplyComposer
              key={r.id}
              row={r}
              totalColumns={5}
              showFullComment={false}
              onToggleShowFullComment={() => {}}
              onSuccess={() => {}}
              onClose={() => {}}
            />
          ))}
        </tbody>
      </table>,
    );
    const first = await screen.findByRole("button", { name: "Generate with AI (requires 2 credits)" });
    await screen.findByRole("button", { name: "Generate with AI (requires 3 credits)" });
    fireEvent.click(first);
    fireEvent.click(screen.getByRole("button", { name: "Generate Professional reply" }));

    await waitFor(() =>
      expect(document.getElementById("credit-status-2")).toHaveTextContent(
        "This shop has 10 credits remaining this month.",
      ),
    );
    expect(document.getElementById("credit-status-1")).toHaveTextContent(
      "This shop has 10 credits remaining this month.",
    );
    expect(screen.getByRole("button", { name: "Generate with AI (requires 3 credits)" })).toBeEnabled();
  });

  it("changes nothing when a generate is aborted", async () => {
    generateSpy.mockRejectedValue(new DOMException("aborted", "AbortError"));
    renderComposer();
    await openPanelAndGenerate("Generate with AI (requires 2 credits)", "Generate Professional reply");
    await act(async () => {});
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("This shop has 35 credits remaining this month.")).toBeInTheDocument();
  });
});

describe("ReplyComposer inactive shop (CRED-INACTIVE-01)", () => {
  it("disables Generate with AI with a reason and keeps manual reply available", async () => {
    renderComposer(fakeRow({ shop_is_active: false }));

    const button = screen.getByRole("button", { name: "Generate with AI" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-describedby", "credit-status-1");
    expect(screen.getByText("AI replies are unavailable for inactive shops.")).toBeInTheDocument();
    expect(costSpy).not.toHaveBeenCalled();

    const box = screen.getByRole("textbox", { name: "Write your reply" });
    expect(box).toBeEnabled();
    fireEvent.change(box, { target: { value: "Thanks" } });
    expect(screen.getByRole("button", { name: "Submit Reply" })).toBeEnabled();
  });
});
