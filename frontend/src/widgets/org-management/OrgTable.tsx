import { useEffect, useState } from "react";
import {
  Eye,
  Pencil,
  Mail,
  Layers,
  Ban,
  CheckCircle,
  Trash2,
} from "lucide-react";
import { DataTable, type DataTableColumn } from "../data-table";
import { RowActionsMenu, type RowAction } from "./RowActionsMenu";
import { ORG_TYPE_LABELS, type OrgRow } from "./types";

/** SA-090: true below the `md` breakpoint (<768px). Table and card layouts need
 * different DOM, so we render one at a time rather than toggling with CSS (which
 * would duplicate every row). Initial value is computed synchronously to avoid a
 * layout flash; falls back to desktop where matchMedia is unavailable (jsdom). */
function useIsMobile(): boolean {
  const query = "(max-width: 767px)";
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && !!window.matchMedia && window.matchMedia(query).matches,
  );
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia(query);
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

export interface OrgTableHandlers {
  onOpenView: (row: OrgRow) => void;
  onOpenEdit: (row: OrgRow) => void;
  onOpenResend: (row: OrgRow) => void;
  onOpenAdjustStores: (row: OrgRow) => void;
  onOpenEnable: (row: OrgRow) => void;
  onOpenDisable: (row: OrgRow) => void;
  onOpenDelete: (row: OrgRow) => void;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const day = String(d.getDate()).padStart(2, "0");
  const month = d.toLocaleString("en", { month: "short" });
  return `${day} ${month} ${d.getFullYear()}`;
}

function StatusBadge({ status }: { status: OrgRow["status"] }) {
  const config = {
    ACTIVE: {
      cls: "bg-green-tint text-[#166534]",
      dot: "bg-green",
      label: "Active",
    },
    DISABLED: {
      cls: "bg-line-soft text-subtle",
      dot: "bg-faint",
      label: "Disabled",
    },
    DELETED: {
      cls: "bg-red-tint text-[#991B1B]",
      dot: "bg-red",
      label: "Deleted",
    },
  } as const;
  const c = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-[999px] text-[12px] font-medium leading-[1.4] whitespace-nowrap ${c.cls}`}
      data-testid={`status-badge-${status.toLowerCase()}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} aria-hidden="true" />
      {c.label}
    </span>
  );
}

function TypeBadge({ type }: { type: OrgRow["org_type"] }) {
  return (
    <span
      className="inline-flex items-center px-2 py-[3px] rounded-[999px] text-[12px] font-medium bg-line-soft text-muted"
      data-testid="type-badge"
    >
      {ORG_TYPE_LABELS[type]}
    </span>
  );
}

export function buildColumns(
  handlers: Pick<OrgTableHandlers, "onOpenView">,
): DataTableColumn<OrgRow>[] {
  return [
    {
      key: "name",
      label: "Name",
      skeletonWidth: "140px",
      accessor: (r) => (
        <button
          type="button"
          onClick={() => handlers.onOpenView(r)}
          aria-label={`View details for ${r.name}`}
          className="text-ink font-semibold text-[13px] hover:text-yellow text-left"
          data-testid={`org-name-${r.id}`}
        >
          {r.name}
        </button>
      ),
    },
    {
      key: "type",
      label: "Type",
      skeletonWidth: "64px",
      accessor: (r) => <TypeBadge type={r.org_type} />,
    },
    {
      key: "email",
      label: "Email",
      skeletonWidth: "180px",
      accessor: (r) => (
        <span className="text-[13px] text-muted">{r.email}</span>
      ),
    },
    {
      key: "stores",
      label: "Stores",
      skeletonWidth: "100px",
      accessor: (r) => (
        <span className="text-[13px]">
          {r.active_stores} used of {r.number_of_stores} allocated
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      skeletonWidth: "64px",
      accessor: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "created",
      label: "Created",
      skeletonWidth: "88px",
      accessor: (r) => (
        <span className="text-[13px] text-muted">{formatDate(r.created_at)}</span>
      ),
    },
  ];
}

export function buildRowActions(handlers: OrgTableHandlers): RowAction[] {
  return [
    {
      key: "view",
      label: "View Details",
      icon: <Eye size={14} aria-hidden="true" />,
      onSelect: handlers.onOpenView,
    },
    {
      key: "edit",
      label: "Edit",
      icon: <Pencil size={14} aria-hidden="true" />,
      onSelect: handlers.onOpenEdit,
    },
    {
      key: "resend",
      label: "Resend Invitation",
      icon: <Mail size={14} aria-hidden="true" />,
      separatorBefore: true,
      visible: (r) => r.activation_status !== "active",
      onSelect: handlers.onOpenResend,
    },
    {
      key: "stores",
      label: "Adjust Store Count",
      icon: <Layers size={14} aria-hidden="true" />,
      onSelect: handlers.onOpenAdjustStores,
    },
    {
      key: "disable",
      label: "Disable",
      icon: <Ban size={14} aria-hidden="true" />,
      tone: "amber",
      separatorBefore: true,
      visible: (r) => r.status === "ACTIVE",
      onSelect: handlers.onOpenDisable,
    },
    {
      key: "enable",
      label: "Enable",
      icon: <CheckCircle size={14} aria-hidden="true" />,
      tone: "green",
      visible: (r) => r.status === "DISABLED",
      onSelect: handlers.onOpenEnable,
    },
    {
      key: "delete",
      label: "Delete",
      icon: <Trash2 size={14} aria-hidden="true" />,
      tone: "red",
      onSelect: handlers.onOpenDelete,
    },
  ];
}

/** SA-090: stacked card layout for the org list on mobile (<768px). Mirrors the
 * table columns as labelled rows so the list never needs horizontal scrolling. */
function OrgCard({
  row,
  actions,
  onOpenView,
}: {
  row: OrgRow;
  actions: RowAction[];
  onOpenView: (row: OrgRow) => void;
}) {
  return (
    <li
      className="bg-white border border-line rounded-card p-4 flex flex-col gap-3"
      data-testid={`org-card-${row.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={() => onOpenView(row)}
          aria-label={`View details for ${row.name}`}
          className="text-ink font-semibold text-[14px] hover:text-yellow text-left break-words"
        >
          {row.name}
        </button>
        <div className="shrink-0">
          <RowActionsMenu row={row} actions={actions} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <TypeBadge type={row.org_type} />
        <StatusBadge status={row.status} />
      </div>
      <dl className="flex flex-col gap-1.5 text-[13px]">
        <div className="flex justify-between gap-3">
          <dt className="text-subtle">Email</dt>
          <dd className="text-muted text-right break-all">{row.email}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-subtle">Stores</dt>
          <dd className="text-ink text-right">
            {row.active_stores} used of {row.number_of_stores} allocated
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-subtle">Created</dt>
          <dd className="text-muted text-right">{formatDate(row.created_at)}</dd>
        </div>
      </dl>
    </li>
  );
}

export function OrgTable({
  rows,
  loading,
  handlers,
}: {
  rows: OrgRow[];
  loading: boolean;
  handlers: OrgTableHandlers;
}) {
  const columns = buildColumns({ onOpenView: handlers.onOpenView });
  const actions = buildRowActions(handlers);
  const isMobile = useIsMobile();

  if (isMobile) {
    if (loading) {
      return (
        <ul className="flex flex-col gap-2" data-testid="org-card-list-loading">
          {Array.from({ length: 4 }).map((_, i) => (
            <li
              key={i}
              className="bg-white border border-line rounded-card p-4 h-[132px] animate-sk-pulse"
            />
          ))}
        </ul>
      );
    }
    if (rows.length === 0) {
      return (
        <div
          className="bg-white border border-line rounded-card p-8 text-center text-[13px] text-muted"
          data-testid="org-card-list-empty"
        >
          No organisations found.
        </div>
      );
    }
    return (
      <ul className="flex flex-col gap-2" data-testid="org-card-list">
        {rows.map((row) => (
          <OrgCard
            key={row.id}
            row={row}
            actions={actions}
            onOpenView={handlers.onOpenView}
          />
        ))}
      </ul>
    );
  }

  return (
    <DataTable<OrgRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(r) => String(r.id)}
      renderRowActions={(row) => (
        <RowActionsMenu row={row} actions={actions} />
      )}
      wrapperClassName="bg-white overflow-hidden"
    />
  );
}
