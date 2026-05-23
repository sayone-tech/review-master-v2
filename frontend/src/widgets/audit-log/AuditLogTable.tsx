// Phase 21-04 — Audit log table.
// Wraps DataTable<AuditLogRow> with 5 columns and a JSON-detail expanded row.

import { AlertCircle, ChevronDown, ChevronRight, ClipboardList, RefreshCw, Search } from "lucide-react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import { ACTION_LABEL, type AuditLogRow } from "./types";
import { TypePill } from "./TypePill";
import { formatRelativeDate } from "./utils";

interface Props {
  rows: AuditLogRow[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
  expandedId: string | null;
  onExpand: (id: string | null) => void;
}

function ExpandButton({
  expanded,
  onClick,
  controls,
}: {
  expanded: boolean;
  onClick: () => void;
  controls: string;
}) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      aria-controls={controls}
      aria-label={expanded ? "Hide details" : "Show details"}
      onClick={onClick}
      className="w-8 h-8 rounded-sm flex items-center justify-center text-muted hover:bg-line-soft hover:text-ink"
    >
      {expanded ? (
        <ChevronDown className="w-4 h-4 text-ink" />
      ) : (
        <ChevronRight className="w-4 h-4" />
      )}
    </button>
  );
}

function EmptyNoData() {
  return (
    <div className="px-4 py-12 text-center">
      <ClipboardList size={40} className="text-faint mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[14px] font-semibold text-ink">No activity logged yet</h3>
      <p className="text-[14px] text-muted mt-1">
        Activity will appear here as your team replies to reviews and manages action items.
      </p>
    </div>
  );
}

function EmptyFiltered({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <div className="px-4 py-12 text-center">
      <Search size={40} className="text-faint mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[14px] font-semibold text-ink">No activity matches your filters</h3>
      <p className="text-[14px] text-muted mt-1">
        Try adjusting the type, date range, or actor filter.
      </p>
      <button
        type="button"
        onClick={onClearFilters}
        className="mt-3 text-[14px] text-muted underline hover:text-ink"
      >
        Clear filters
      </button>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="px-4 py-12 text-center">
      <AlertCircle size={40} className="text-red mx-auto mb-4" aria-hidden="true" />
      <h3 className="text-[14px] font-semibold text-ink">Could not load activity log</h3>
      <p className="text-[14px] text-muted mt-1">Something went wrong. Please try again.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white border border-line rounded-md text-[14px] font-semibold text-ink hover:bg-line-soft"
      >
        <RefreshCw size={14} />
        Retry
      </button>
    </div>
  );
}

export function AuditLogTable({
  rows,
  loading,
  error,
  onRetry,
  hasActiveFilters,
  onClearFilters,
  expandedId,
  onExpand,
}: Props) {
  if (error && !loading) {
    return <ErrorState onRetry={onRetry} />;
  }

  const columns: DataTableColumn<AuditLogRow>[] = [
    {
      key: "created_at",
      label: "Date / Time",
      skeletonWidth: "120px",
      accessor: (row) => (
        <time
          dateTime={row.created_at}
          title={new Date(row.created_at).toLocaleString()}
          className="text-text"
        >
          {formatRelativeDate(row.created_at)}
        </time>
      ),
    },
    {
      key: "actor_name",
      label: "Actor",
      skeletonWidth: "100px",
      accessor: (row) =>
        row.actor_name ? (
          <span className="text-text">{row.actor_name}</span>
        ) : (
          <span className="text-muted italic">System</span>
        ),
    },
    {
      key: "entity_type",
      label: "Type",
      skeletonWidth: "60px",
      accessor: (row) => <TypePill entityType={row.entity_type} />,
    },
    {
      key: "action",
      label: "Action",
      skeletonWidth: "140px",
      accessor: (row) => {
        const label = ACTION_LABEL[row.action];
        return label ? (
          <span className="text-text">{label}</span>
        ) : (
          <span className="text-muted">{row.action}</span>
        );
      },
    },
    {
      key: "details",
      label: "Details",
      skeletonWidth: "24px",
      accessor: (row) => (
        <ExpandButton
          expanded={expandedId === row.id}
          controls={`audit-log-details-${row.id}`}
          onClick={() => onExpand(expandedId === row.id ? null : row.id)}
        />
      ),
    },
  ];

  return (
    <DataTable<AuditLogRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(r) => r.id}
      wrapperClassName="bg-white"
      renderExpanded={(row) => {
        if (expandedId !== row.id) return null;
        return (
          <tr
            key={`exp-${row.id}`}
            id={`audit-log-details-${row.id}`}
            role="region"
            className="bg-[#FAFAFA] border-b border-line"
          >
            <td colSpan={5} className="px-4 py-3">
              <pre className="text-[12px] font-mono text-text whitespace-pre-wrap break-all leading-relaxed max-h-48 overflow-y-auto">
                {JSON.stringify(row.after_data, null, 2)}
              </pre>
            </td>
          </tr>
        );
      }}
      emptyState={hasActiveFilters ? <EmptyFiltered onClearFilters={onClearFilters} /> : <EmptyNoData />}
    />
  );
}
