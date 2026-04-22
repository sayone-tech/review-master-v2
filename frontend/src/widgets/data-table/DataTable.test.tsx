import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable, type DataTableColumn } from "./index";

interface Row {
  id: string;
  name: string;
  stores: number;
}

const columns: DataTableColumn<Row>[] = [
  { key: "name", label: "Organisation", accessor: (r) => r.name, skeletonWidth: "140px" },
  { key: "stores", label: "Stores", accessor: (r) => r.stores, align: "right", skeletonWidth: "40px" },
];

describe("DataTable", () => {
  it("renders 6 skeleton rows when loading", () => {
    render(<DataTable columns={columns} rows={[]} loading rowKey={(r) => r.id} />);
    const skRows = screen.getAllByTestId("data-table-skeleton-row");
    expect(skRows).toHaveLength(6);
  });

  it("renders empty state when not loading and rows empty", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        loading={false}
        emptyState={<div data-testid="empty">No data</div>}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByTestId("empty")).toBeInTheDocument();
  });

  it("renders one tr per row when populated", () => {
    const rows: Row[] = [
      { id: "1", name: "Acme", stores: 4 },
      { id: "2", name: "Bravo", stores: 7 },
    ];
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    const dataRows = screen.getAllByTestId("data-table-row");
    expect(dataRows).toHaveLength(2);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Bravo")).toBeInTheDocument();
  });

  it("row actions have opacity-35 default and group-hover:opacity-100", () => {
    const rows: Row[] = [{ id: "1", name: "Acme", stores: 4 }];
    render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        renderRowActions={(r) => <button>Actions for {r.name}</button>}
      />,
    );
    const btn = screen.getByText("Actions for Acme");
    const wrapper = btn.parentElement;
    expect(wrapper?.className).toContain("opacity-35");
    expect(wrapper?.className).toContain("group-hover:opacity-100");
  });
});
