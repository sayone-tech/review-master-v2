import { Fragment, useEffect, useRef, type ReactNode } from "react";
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
  /**
   * Optional: render an extra `<tr>` immediately below the row (accordion pattern).
   * Returning `null` for a row means "no expansion for this row".
   * The callback MUST return a `<tr>` element with a `<td colSpan={colSpan}>` so it
   * spans all columns. The DataTable computes `colSpan = columns.length + (renderRowActions ? 1 : 0)`.
   */
  renderExpanded?: (row: T) => ReactNode;
  /** Override the outer wrapper className. Defaults to the standard card style. */
  wrapperClassName?: string;
  // Phase 18 — Multi-select checkbox column (all optional; existing consumers untouched).
  /** When defined, a leading checkbox column is rendered. */
  selectedIds?: Set<string>;
  /** Called when a row's checkbox is toggled. */
  onToggleRow?: (key: string) => void;
  /** Called when the header "select all" checkbox is toggled. Receives every
   * selectable row key currently on the page. */
  onToggleAll?: (allKeys: string[]) => void;
  /** Optional gating: return false to disable the checkbox for a row. */
  isRowSelectable?: (row: T) => boolean;
}

export function DataTable<T>({
  columns,
  rows,
  loading = false,
  emptyState,
  renderRowActions,
  rowKey,
  renderExpanded,
  wrapperClassName = "bg-white border border-line rounded-card overflow-hidden",
  selectedIds,
  onToggleRow,
  onToggleAll,
  isRowSelectable,
}: DataTableProps<T>) {
  const hasSelection = selectedIds !== undefined;
  const colSpan =
    columns.length + (renderRowActions ? 1 : 0) + (hasSelection ? 1 : 0);

  // Compute selectable row keys for the current page.
  const selectableKeys = hasSelection
    ? rows.filter((r) => (isRowSelectable ? isRowSelectable(r) : true)).map(rowKey)
    : [];
  const selectedSelectableCount = hasSelection
    ? selectableKeys.filter((k) => selectedIds.has(k)).length
    : 0;
  const allSelected =
    hasSelection && selectableKeys.length > 0 && selectedSelectableCount === selectableKeys.length;
  const someSelected =
    hasSelection && selectedSelectableCount > 0 && !allSelected;

  // Apply indeterminate state on the header checkbox.
  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <div
      className={wrapperClassName}
      data-testid="data-table-wrap"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13.5px] text-text border-collapse">
          <thead>
            <tr>
              {hasSelection && (
                <th
                  className="w-10 px-4 py-[11px] bg-[#FBFBFB] border-b border-line sticky top-0 z-10"
                  aria-label="Select all AI-extracted items"
                >
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    className="w-4 h-4 accent-[#FACC15] cursor-pointer disabled:cursor-not-allowed disabled:opacity-40"
                    checked={allSelected}
                    disabled={selectableKeys.length === 0}
                    onChange={() => onToggleAll?.(selectableKeys)}
                    aria-label="Select all AI-extracted items"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-[11px] text-[12px] font-medium text-subtle uppercase tracking-[0.05em] bg-[#FBFBFB] border-b border-line sticky top-0 z-10 ${col.align === "right" ? "text-right" : "text-left"}`}
                >
                  {col.label}
                </th>
              ))}
              {renderRowActions && (
                <th
                  className="px-4 py-[11px] bg-[#FBFBFB] border-b border-line sticky top-0 z-10 w-12"
                  aria-label="Actions"
                ></th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr
                  key={`sk-${i}`}
                  data-testid="data-table-skeleton-row"
                  aria-busy="true"
                >
                  {hasSelection && (
                    <td className="w-10 px-4 py-[14px] border-b border-line-soft">
                      <span
                        className="inline-block w-4 h-4 bg-line rounded-sm animate-sk-pulse"
                        aria-hidden="true"
                      />
                    </td>
                  )}
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
            ) : rows.length === 0 && emptyState ? (
              <tr data-testid="data-table-empty-row">
                <td colSpan={colSpan}>{emptyState}</td>
              </tr>
            ) : (
              rows.map((row) => {
                const expanded = renderExpanded ? renderExpanded(row) : null;
                const key = rowKey(row);
                const selectable = !hasSelection || (isRowSelectable ? isRowSelectable(row) : true);
                const checked = hasSelection && selectedIds.has(key);
                return (
                  <Fragment key={key}>
                    <tr
                      className="group hover:bg-[#FBFBFB] [&:last-child>td]:border-b-0"
                      data-testid="data-table-row"
                    >
                      {hasSelection && (
                        <td className="w-10 px-4 py-[14px] border-b border-line-soft align-middle">
                          <input
                            type="checkbox"
                            className={`w-4 h-4 accent-[#FACC15] ${selectable ? "cursor-pointer" : "opacity-40 cursor-not-allowed"}`}
                            checked={checked}
                            disabled={!selectable}
                            onChange={() => {
                              if (selectable) onToggleRow?.(key);
                            }}
                            aria-label={`Select ${key}`}
                          />
                        </td>
                      )}
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
                    {expanded}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export { MoreHorizontal };
