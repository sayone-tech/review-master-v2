import type { ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";

export interface DataTableColumn<T> {
  key: string;
  label: string;
  /** Accessor: maps row to cell content (ReactNode). */
  accessor: (row: T) => ReactNode;
  /** Header alignment. */
  align?: "left" | "right";
  /** Optional width for skeleton cell. */
  skeletonWidth?: string;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  loading?: boolean;
  emptyState?: ReactNode;
  /** Render the row actions cell (three-dot menu + dropdown). */
  renderRowActions?: (row: T) => ReactNode;
  /** Unique row key accessor. */
  rowKey: (row: T) => string;
}

export function DataTable<T>({
  columns,
  rows,
  loading = false,
  emptyState,
  renderRowActions,
  rowKey,
}: DataTableProps<T>) {
  if (!loading && rows.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div
      className="bg-white border border-line rounded-card overflow-hidden"
      data-testid="data-table-wrap"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13.5px] text-text">
          <thead className="bg-[#FBFBFB] sticky top-0">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-[11px] text-[12px] font-medium text-subtle uppercase tracking-[0.05em] border-b border-line ${col.align === "right" ? "text-right" : "text-left"}`}
                >
                  {col.label}
                </th>
              ))}
              {renderRowActions && (
                <th
                  className="px-4 py-[11px] border-b border-line w-12"
                  aria-label="Actions"
                ></th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr
                    key={`sk-${i}`}
                    data-testid="data-table-skeleton-row"
                    aria-busy="true"
                  >
                    {columns.map((col) => (
                      <td key={col.key} className="px-4 py-[14px] border-b border-line-soft">
                        <span
                          className="inline-block bg-line rounded-sm animate-sk-pulse"
                          style={{ width: col.skeletonWidth || "120px", height: "14px" }}
                          aria-hidden="true"
                        />
                      </td>
                    ))}
                    {renderRowActions && (
                      <td className="px-4 py-[14px] border-b border-line-soft">
                        <span
                          className="inline-block w-5 h-5 bg-line rounded-sm animate-sk-pulse"
                          aria-hidden="true"
                        />
                      </td>
                    )}
                  </tr>
                ))
              : rows.map((row) => (
                  <tr
                    key={rowKey(row)}
                    className="group hover:bg-[#FBFBFB]"
                    data-testid="data-table-row"
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={`px-4 py-[14px] border-b border-line-soft align-middle ${col.align === "right" ? "text-right" : ""}`}
                      >
                        {col.accessor(row)}
                      </td>
                    ))}
                    {renderRowActions && (
                      <td className="px-4 py-[14px] border-b border-line-soft">
                        <span className="opacity-35 group-hover:opacity-100 transition-opacity">
                          {renderRowActions(row)}
                        </span>
                      </td>
                    )}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export { MoreHorizontal };
