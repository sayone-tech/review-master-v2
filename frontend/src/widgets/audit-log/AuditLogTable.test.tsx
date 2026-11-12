import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuditLogTable } from "./AuditLogTable";
import type { AuditLogRow } from "./types";

function fakeRow(over: Partial<AuditLogRow> = {}): AuditLogRow {
  return {
    id: "1",
    created_at: "2026-11-01T10:00:00Z",
    entity_type: "shop",
    entity_id: "7",
    action: "shop.credits.consumed",
    actor_id: null,
    actor_name: null,
    shop_name: "Downtown Store",
    after_data: null,
    ...over,
  };
}

function renderTable(rows: AuditLogRow[]) {
  return render(
    <AuditLogTable
      rows={rows}
      loading={false}
      error={null}
      onRetry={() => {}}
      hasActiveFilters={false}
      onClearFilters={() => {}}
      expandedId={null}
      onExpand={() => {}}
    />,
  );
}

describe("AuditLogTable credit rows", () => {
  it("should render Credits pill and shop name when row is a shop credit event", () => {
    renderTable([fakeRow()]);
    expect(screen.getByText("Credits")).toBeTruthy();
    expect(screen.getByText("Credits used")).toBeTruthy();
    expect(screen.getByText("— Downtown Store")).toBeTruthy();
  });

  it.each([
    ["shop.credits.allocated", "Credits allocated"],
    ["shop.credits.bonus_allocated", "Bonus credits added"],
    ["shop.credits.consumed", "Credits used"],
    ["shop.credits.late_commit", "Credits used (late)"],
    ["shop.credits.refunded", "Credits refunded"],
    ["shop.credits.lapsed", "Credits lapsed"],
  ])("should render label for %s when row is a shop credit event", (action, label) => {
    renderTable([fakeRow({ action })]);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("should render Credits pill for both shop and organisation rows", () => {
    renderTable([
      fakeRow({ id: "1" }),
      fakeRow({
        id: "2",
        entity_type: "organisation",
        action: "organisation.credits.set",
        shop_name: null,
      }),
    ]);
    expect(screen.getAllByText("Credits")).toHaveLength(2);
  });

  it("should keep Reply and Action Item pills when rows are not credit events", () => {
    renderTable([
      fakeRow({ id: "1", entity_type: "review", action: "reply_posted", shop_name: null }),
      fakeRow({
        id: "2",
        entity_type: "action_item",
        action: "action_item.created",
        shop_name: null,
      }),
    ]);
    expect(screen.getByText("Reply")).toBeTruthy();
    expect(screen.getByText("Action Item")).toBeTruthy();
    expect(screen.queryByText(/\u2014/)).toBeNull();
  });

  it("should render Shop #id fallback when shop_name is null", () => {
    renderTable([fakeRow({ entity_id: "42", shop_name: null })]);
    expect(screen.getByText("\u2014 Shop #42")).toBeTruthy();
  });

  it("should render the label only when row is organisation.credits.set", () => {
    renderTable([
      fakeRow({
        entity_type: "organisation",
        entity_id: "3",
        action: "organisation.credits.set",
        shop_name: null,
      }),
    ]);
    expect(screen.getByText("Monthly credits updated")).toBeTruthy();
    expect(screen.queryByText(/\u2014/)).toBeNull();
  });

  it("should render raw action plus shop suffix when the credit action is unknown", () => {
    renderTable([fakeRow({ action: "shop.credits.mystery" })]);
    expect(screen.getByText("shop.credits.mystery")).toBeTruthy();
    expect(screen.getByText("\u2014 Downtown Store")).toBeTruthy();
  });

  it("should render a 120-character shop name in full inside a wrapping element", () => {
    const longName = "A".repeat(120);
    renderTable([fakeRow({ shop_name: longName })]);
    const suffix = screen.getByText(`\u2014 ${longName}`);
    expect(suffix.className).toContain("break-words");
  });

  it("should render System when the actor is null", () => {
    renderTable([fakeRow({ actor_name: null })]);
    expect(screen.getByText("System")).toBeTruthy();
  });
});

describe("AuditLogTable AI reply rows (CVIS-06)", () => {
  it("should show credit count and review when a credit row is per-review", () => {
    renderTable([fakeRow({ after_data: { credits: 2, review_id: 41, outcome: "success" } })]);
    expect(screen.getByText("Credits used: 2")).toBeTruthy();
    expect(screen.getByText("— Downtown Store · Review #41")).toBeTruthy();
  });

  it("should show the tone when the row is ai_reply_generated", () => {
    renderTable([
      fakeRow({
        entity_type: "review",
        entity_id: "41",
        action: "ai_reply_generated",
        shop_name: null,
        after_data: { tone: "professional", ai_usage_log_id: 9 },
      }),
    ]);
    expect(screen.getByText("AI reply generated (Professional)")).toBeTruthy();
    expect(screen.getByText("Reply")).toBeTruthy();
  });

  it("should fall back to the plain label when ai_reply_generated has no known tone", () => {
    renderTable([
      fakeRow({ entity_type: "review", action: "ai_reply_generated", after_data: null }),
    ]);
    expect(screen.getByText("AI reply generated")).toBeTruthy();
  });
});
