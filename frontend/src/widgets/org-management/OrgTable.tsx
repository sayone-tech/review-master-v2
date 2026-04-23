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
  return (
    <DataTable<OrgRow>
      columns={columns}
      rows={rows}
      loading={loading}
      rowKey={(r) => String(r.id)}
      renderRowActions={(row) => (
        <RowActionsMenu row={row} actions={actions} />
      )}
    />
  );
}
