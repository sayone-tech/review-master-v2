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
});
