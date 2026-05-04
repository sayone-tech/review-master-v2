import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, MoreHorizontal, Sparkles, User } from "lucide-react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import { StatusBadge } from "./StatusBadge";
import { ScopePill } from "./ScopePill";
import type { ActionItemListRow, ActionItemStatus } from "./types";
import { STATUS_LABEL } from "./types";

function avatarInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths === 1) return "1 month ago";
  if (diffMonths < 12) return `${diffMonths} months ago`;
  const diffYears = Math.floor(diffMonths / 12);
  return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function isOverdue(dueDate: string): boolean {
  const today = new Date(new Date().toDateString());
  const d = new Date(dueDate);
  return d < today;
}

interface RowMenuProps {
  row: ActionItemListRow;
  onOpenModal: (id: number) => void;
  onTransitionStatus: (id: number, status: ActionItemStatus) => void;
}

const STATUS_ORDER: ActionItemStatus[] = ["TODO", "IN_PROGRESS", "COMPLETE", "WONT_DO"];

function RowMenu({ row, onOpenModal, onTransitionStatus }: RowMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-8 h-8 rounded-md text-muted hover:bg-line-soft hover:text-ink flex items-center justify-center"
        aria-label={`More actions for ${row.title}`}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreHorizontal size={14} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-1 w-[200px] bg-white border border-line rounded-menu shadow-lg py-1 z-50"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onOpenModal(row.id);
            }}
            className="w-full text-left px-4 py-2 text-[14px] text-ink hover:bg-line-soft cursor-pointer"
          >
            Open details
          </button>
          <div className="border-t border-line-soft mt-1 pt-1">
            <div
              role="group"
              aria-label="Change status"
              className="px-4 py-1 text-[12px] uppercase font-normal text-subtle tracking-[0.05em]"
            >
              CHANGE STATUS
            </div>
            {STATUS_ORDER.map((s) => {
              const active = s === row.status;
              return (
                <button
                  key={s}
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpen(false);
                    onTransitionStatus(row.id, s);
                  }}
                  className={`w-full text-left px-4 py-2 text-[14px] hover:bg-line-soft cursor-pointer flex items-center gap-2 ${
                    active ? "font-semibold text-ink" : "font-normal text-ink"
                  }`}
                >
                  <span className="w-3.5 inline-flex items-center justify-center">
                    {active && <Check size={14} className="text-green" aria-hidden="true" />}
                  </span>
                  <span>{STATUS_LABEL[s]}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

interface Props {
  rows: ActionItemListRow[];
  loading: boolean;
  emptyState: ReactNode;
  onOpenModal: (id: number) => void;
  onTransitionStatus: (id: number, status: ActionItemStatus) => void;
}

export function ActionItemTable({
  rows,
  loading,
  emptyState,
  onOpenModal,
  onTransitionStatus,
}: Props) {
  const columns: DataTableColumn<ActionItemListRow>[] = [
    {
      key: "title",
      label: "TITLE",
      skeletonWidth: "180px",
      accessor: (r) => (
        <button
          type="button"
          onClick={() => onOpenModal(r.id)}
          className="text-[14px] text-ink font-semibold cursor-pointer hover:underline text-left"
          aria-label={`${r.title} — open action item`}
        >
          {r.title}
        </button>
      ),
    },
    {
      key: "status",
      label: "STATUS",
      skeletonWidth: "80px",
      accessor: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "scope",
      label: "SCOPE",
      skeletonWidth: "80px",
      accessor: (r) => <ScopePill scope={r.scope} />,
    },
    {
      key: "shop",
      label: "SHOP",
      skeletonWidth: "120px",
      accessor: (r) => (
        <span className="text-[14px] text-ink">{r.shop_name ?? "—"}</span>
      ),
    },
    {
      key: "assignee",
      label: "ASSIGNEE",
      skeletonWidth: "120px",
      accessor: (r) =>
        r.assignee_name ? (
          <span className="flex items-center gap-2 text-[14px] text-ink">
            <span className="w-6 h-6 rounded-full bg-line flex items-center justify-center text-[11px] font-semibold text-muted shrink-0">
              {avatarInitials(r.assignee_name)}
            </span>
            {r.assignee_name}
          </span>
        ) : (
          <span className="text-muted text-[14px]">Unassigned</span>
        ),
    },
    {
      key: "due_date",
      label: "DUE",
      skeletonWidth: "80px",
      accessor: (r) => {
        if (!r.due_date) return <span className="text-muted">—</span>;
        const overdue = isOverdue(r.due_date);
        return (
          <span
            className={
              overdue ? "text-red font-semibold text-[12px]" : "text-[14px] text-ink"
            }
            aria-label={overdue ? `${r.due_date} — overdue` : undefined}
          >
            {formatDate(r.due_date)}
          </span>
        );
      },
    },
    {
      key: "created",
      label: "CREATED",
      skeletonWidth: "80px",
      accessor: (r) => (
        <span className="text-[14px] text-muted">{formatRelativeDate(r.created_at)}</span>
      ),
    },
    {
      key: "source",
      label: "SOURCE",
      skeletonWidth: "40px",
      accessor: (r) =>
        r.source === "AI" ? (
          <Sparkles
            size={14}
            className="text-muted"
            aria-hidden="true"
          >
            <title>AI extracted</title>
          </Sparkles>
        ) : (
          <User
            size={14}
            className="text-muted"
            aria-hidden="true"
          >
            <title>Manually created</title>
          </User>
        ),
    },
  ];

  return (
    <DataTable<ActionItemListRow>
      columns={columns}
      rows={rows}
      loading={loading}
      emptyState={emptyState}
      rowKey={(r) => String(r.id)}
      renderRowActions={(row) => (
        <RowMenu
          row={row}
          onOpenModal={onOpenModal}
          onTransitionStatus={onTransitionStatus}
        />
      )}
    />
  );
}
