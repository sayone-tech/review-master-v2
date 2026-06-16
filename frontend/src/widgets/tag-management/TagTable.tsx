// Phase 25-03 — Sortable data table for canonical tags.
// Wraps DataTable<OrgCanonicalTagRow> with 5 columns + inline rename + actions menu.

import { ChevronDown, ChevronUp, Tag } from "lucide-react";
import { useState } from "react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import { PolarityBadge } from "./PolarityBadge";
import { RenameInput } from "./RenameInput";
import { TagActionsMenu } from "./TagActionsMenu";
import type { OrgCanonicalTagRow } from "./types";

interface Props {
  rows: OrgCanonicalTagRow[];
  loading: boolean;
  error: string | null;
  ordering: string;
  onToggleOrdering: (col: "label" | "review_count" | "created_at") => void;
  onRetry: () => void;
  onRowRenamed: (updated: OrgCanonicalTagRow) => void;
  onMergeSource: (row: OrgCanonicalTagRow) => void;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

type SortCol = "label" | "review_count" | "created_at";

function SortHeader({
  label,
  col,
  ordering,
  onToggle,
}: {
  label: string;
  col: SortCol;
  ordering: string;
  onToggle: (col: SortCol) => void;
}) {
  const isAsc = ordering === col;
  const isDesc = ordering === `-${col}`;
  const active = isAsc || isDesc;
  const ariaSortVal = isAsc ? "ascending" : isDesc ? "descending" : "none";

  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 text-[12px] font-semibold uppercase tracking-[0.05em] text-subtle hover:text-ink"
      onClick={() => onToggle(col)}
      aria-sort={ariaSortVal as "ascending" | "descending" | "none"}
    >
      {label}
      {active &&
        (isAsc ? (
          <ChevronUp size={12} className="text-muted" aria-hidden="true" />
        ) : (
          <ChevronDown size={12} className="text-muted" aria-hidden="true" />
        ))}
    </button>
  );
}

export function TagTable({
  rows,
  loading,
  error,
  ordering,
  onToggleOrdering,
  onRetry,
  onRowRenamed,
  onMergeSource,
}: Props) {
  const [renamingId, setRenamingId] = useState<number | null>(null);

  const handleSaved = (updated: OrgCanonicalTagRow) => {
    setRenamingId(null);
    onRowRenamed(updated);
  };

  const emptyState =
    rows.length === 0 && !loading ? (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <Tag size={32} className="text-faint" aria-hidden="true" />
        <h3 className="text-[14px] font-semibold text-ink">No canonical tags yet</h3>
        <p className="text-[12px] text-muted text-center max-w-[280px]">
          Tags will appear here once reviews have been enriched. Check back after your first sync
          completes.
        </p>
      </div>
    ) : null;

  const columns: DataTableColumn<OrgCanonicalTagRow>[] = [
    {
      key: "label",
      label: "LABEL",
      skeletonWidth: "180px",
      accessor: (row) => {
        if (renamingId === row.id) {
          return (
            <RenameInput
              row={row}
              onSaved={handleSaved}
              onCancel={() => setRenamingId(null)}
            />
          );
        }
        return <span className="text-[14px] text-ink">{row.label}</span>;
      },
    },
    {
      key: "polarity_type",
      label: "POLARITY",
      skeletonWidth: "80px",
      accessor: (row) => <PolarityBadge polarity={row.polarity_type} />,
    },
    {
      key: "review_count",
      label: "REVIEWS",
      align: "right",
      skeletonWidth: "40px",
      accessor: (row) => (
        <span className="text-[14px] text-ink tabular-nums">{row.review_count}</span>
      ),
    },
    {
      key: "first_seen",
      label: "FIRST SEEN",
      skeletonWidth: "80px",
      accessor: (row) => (
        <span className="text-[14px] text-subtle">{formatDate(row.first_seen)}</span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <h3 className="text-[14px] font-semibold text-ink">Could not load tags</h3>
        <p className="text-[12px] text-muted">Something went wrong. Please try again.</p>
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 text-[13px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover"
        >
          Reload Tags
        </button>
      </div>
    );
  }

  return (
    <DataTable<OrgCanonicalTagRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(row) => String(row.id)}
      emptyState={emptyState}
      wrapperClassName="bg-white"
      renderRowActions={(row) => (
        <TagActionsMenu
          row={row}
          onRename={() => setRenamingId(row.id)}
          onMerge={() => onMergeSource(row)}
        />
      )}
    />
  );
}

export { SortHeader };
