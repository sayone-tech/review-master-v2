import { type ReactNode } from "react";
import { Modal } from "../modal/Modal";
import { ConnectionStatusPill } from "./ConnectionStatusPill";
import type { ShopRow } from "./types";
import { SYNC_DEPTH_LABELS } from "./types";

interface Props {
  open: boolean;
  shop: ShopRow | null;
  isOrgAdmin: boolean;
  onClose: () => void;
  onEdit: () => void;
  onActivate: () => void;
  onDeactivate: () => void;
  onReconnect: () => void;
}

const dtCls = "text-[11.5px] font-semibold text-subtle tracking-[0.05em] uppercase mb-0.5";
const ddCls = "text-[13.5px] text-ink";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className={dtCls}>{label}</dt>
      <dd className={ddCls}>{children}</dd>
    </div>
  );
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function ShopDetailsModal({
  open,
  shop,
  isOrgAdmin: _isOrgAdmin,
  onClose,
  onEdit,
  onActivate,
  onDeactivate,
  onReconnect,
}: Props) {
  const showReconnect =
    shop?.connection_method === "GOOGLE_OAUTH" &&
    (shop.connection_status === "ERROR" || shop.connection_status === "EXPIRED");

  const handleModalClose = () => {
    onClose();
  };

  return (
    <Modal
        open={open}
        title="Shop Details"
        size="lg"
        onClose={handleModalClose}
        footer={
          <>
            {showReconnect && (
              <button
                type="button"
                onClick={onReconnect}
                className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover"
              >
                Reconnect Google
              </button>
            )}
            <button
              type="button"
              onClick={onEdit}
              className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            >
              Edit
            </button>
            {shop?.is_active ? (
              <button
                type="button"
                onClick={onDeactivate}
                className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              >
                Deactivate
              </button>
            ) : (
              <button
                type="button"
                onClick={onActivate}
                className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              >
                Activate
              </button>
            )}
            <button
              type="button"
              onClick={handleModalClose}
              className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
            >
              Close
            </button>
          </>
        }
      >
        {shop ? (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
            <Row label="Shop Name">{shop.name}</Row>
            <Row label="Phone">{shop.phone || "—"}</Row>
            <Row label="Region">
              {shop.region_region_id ? (
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
                    style={{ backgroundColor: "#F3F4F6", color: "#374151" }}
                  >
                    {shop.region_region_id}
                  </span>
                  {shop.region_name}
                </span>
              ) : (
                "—"
              )}
            </Row>
            <Row label="Status">
              <span
                className="inline-flex items-center rounded-full px-2 py-[3px] text-[12px] font-medium"
                style={
                  shop.is_active
                    ? { backgroundColor: "#F0FDF4", color: "#16A34A" }
                    : { backgroundColor: "#F9FAFB", color: "#6B7280" }
                }
              >
                {shop.is_active ? "Active" : "Inactive"}
              </span>
            </Row>
            <Row label="Street Address">{shop.street_address || "—"}</Row>
            <Row label="Place ID">
              <code className="font-mono text-[12.5px]">{shop.place_id || "—"}</code>
            </Row>
            <Row label="Connection Method">
              {shop.connection_method === "GOOGLE_OAUTH" ? "Google OAuth" : "Not connected"}
            </Row>
            <Row label="Connection Status">
              <ConnectionStatusPill
                method={shop.connection_method}
                status={shop.connection_status}
              />
            </Row>
            <Row label="Review history">{SYNC_DEPTH_LABELS[shop.sync_depth]}</Row>
            <Row label="Created">{formatDate(shop.created_at)}</Row>
            <Row label="Updated">{formatDate(shop.updated_at)}</Row>
          </dl>
        ) : (
          <p className="text-[13.5px] text-muted">No shop selected.</p>
        )}
    </Modal>
  );
}
