import { Modal } from "../modal";
import { ORG_TYPE_LABELS, type OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onEdit: (row: OrgRow) => void;
  onResend: (row: OrgRow) => void;
}

const ACTIVATION_LABEL = {
  active: { text: "Active", dot: "bg-green" },
  pending: { text: "Pending invite", dot: "bg-amber" },
  expired: { text: "Invitation expired", dot: "bg-faint" },
} as const;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")} ${d.toLocaleString("en", { month: "short" })} ${d.getFullYear()}`;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return `${formatDate(iso)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function ViewOrgModal({ org, onClose, onEdit, onResend }: Props) {
  if (!org) return null;
  const actLabel = ACTIVATION_LABEL[org.activation_status];
  return (
    <Modal
      open={true}
      onClose={onClose}
      title={org.name}
      size="default"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Close
          </button>
          {org.activation_status !== "active" && (
            <button
              type="button"
              onClick={() => onResend(org)}
              className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              data-testid="view-resend-btn"
            >
              Resend Invitation
            </button>
          )}
          <button
            type="button"
            onClick={() => onEdit(org)}
            className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
            data-testid="view-edit-btn"
          >
            Edit
          </button>
        </>
      }
    >
      <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-3">
        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Type
        </dt>
        <dd className="text-[13px] text-ink">{ORG_TYPE_LABELS[org.org_type]}</dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Email
        </dt>
        <dd className="text-[13px] text-ink">{org.email}</dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Address
        </dt>
        <dd className="text-[13px] text-ink">{org.address || "—"}</dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Stores
        </dt>
        <dd className="text-[13px] text-ink">
          {org.active_stores} used of {org.number_of_stores} allocated
        </dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Status
        </dt>
        <dd className="text-[13px] text-ink">
          {org.status === "ACTIVE"
            ? "Active"
            : org.status === "DISABLED"
              ? "Disabled"
              : "Deleted"}
        </dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Created
        </dt>
        <dd className="text-[13px] text-ink">{formatDate(org.created_at)}</dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Org Admin
        </dt>
        <dd className="text-[13px] text-ink flex items-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full ${actLabel.dot}`}
            aria-hidden="true"
          />
          {actLabel.text}
        </dd>

        <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">
          Last invite
        </dt>
        <dd className="text-[13px] text-ink">
          {formatDateTime(org.last_invited_at)}
        </dd>
      </dl>
    </Modal>
  );
}
