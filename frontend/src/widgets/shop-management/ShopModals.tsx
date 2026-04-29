import { useCallback, useEffect, useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { Modal } from "../modal/Modal";
import { CreateShopModal } from "./CreateShopModal";
import { EditShopModal } from "./EditShopModal";
import { ShopDetailsModal } from "./ShopDetailsModal";
import { RevealKeyModal } from "./RevealKeyModal";
import { RotateKeyModal } from "./RotateKeyModal";
import { OAuthConnectionSection } from "./OAuthConnectionSection";
import { activateShop, deactivateShop, reconnectShop } from "./api";
import { emitToast } from "../../lib/toast";
import type { AllocationStatus, ShopRow } from "./types";

interface RegionLite {
  id: number;
  region_id: string;
  name: string;
}

/**
 * CreateButtonBridge wires up the Django-template-rendered "+ Add Shop" button
 * and the empty-state CTA to open the Create modal. Intercepts at-limit clicks
 * and shows a toast instead of opening the modal.
 */
function CreateButtonBridge({
  onOpen,
  allocationAtLimit,
}: {
  onOpen: () => void;
  allocationAtLimit: boolean;
}) {
  useEffect(() => {
    const ids = ["open-create-shop", "open-create-shop-empty"];
    const handlers: Array<{ btn: HTMLElement; handler: (e: Event) => void }> = [];
    for (const id of ids) {
      const btn = document.getElementById(id);
      if (!btn) continue;
      const handler = (e: Event) => {
        // Check both the prop and the DOM attribute — the attribute is set by Django template
        const atLimit =
          allocationAtLimit || btn.getAttribute("data-at-limit") === "true";
        if (atLimit && id === "open-create-shop") {
          e.preventDefault();
          emitToast({
            kind: "error",
            title: "You've reached your shop limit. Contact support to increase.",
          });
          return;
        }
        onOpen();
      };
      btn.addEventListener("click", handler);
      handlers.push({ btn, handler });
    }
    return () => handlers.forEach(({ btn, handler }) => btn.removeEventListener("click", handler));
  }, [onOpen, allocationAtLimit]);
  return null;
}

interface ShopModalsProps {
  allocation: AllocationStatus;
  regions: RegionLite[];
}

export function ShopModals({ allocation, regions }: ShopModalsProps) {
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<ShopRow | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [revealOpen, setRevealOpen] = useState(false);
  const [rotateOpen, setRotateOpen] = useState(false);
  const [reconnectOpen, setReconnectOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleOpenCreate = useCallback(() => setCreateOpen(true), []);

  // Listen for CustomEvents from ShopTable (Plan 08-04)
  useEffect(() => {
    const map: Array<[string, (e: Event) => void]> = [
      [
        "shop:open-details",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setDetailsOpen(true);
        },
      ],
      [
        "shop:open-edit",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setEditOpen(true);
        },
      ],
      [
        "shop:open-deactivate",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setDeactivateOpen(true);
        },
      ],
      [
        "shop:open-activate",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setActivateOpen(true);
        },
      ],
      [
        "shop:open-reveal-key",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setRevealOpen(true);
        },
      ],
      [
        "shop:open-rotate-key",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setRotateOpen(true);
        },
      ],
      [
        "shop:open-reconnect",
        (e) => {
          setSelected((e as CustomEvent<ShopRow>).detail);
          setReconnectOpen(true);
        },
      ],
    ];
    map.forEach(([n, h]) => window.addEventListener(n, h));
    return () => map.forEach(([n, h]) => window.removeEventListener(n, h));
  }, []);

  function refresh() {
    window.dispatchEvent(new CustomEvent("shop:refresh"));
  }

  async function handleDeactivateConfirm() {
    if (!selected) return;
    setSubmitting(true);
    try {
      await deactivateShop(selected.id);
      emitToast({ kind: "success", title: `Shop '${selected.name}' deactivated.` });
      refresh();
      setDeactivateOpen(false);
      setSelected(null);
    } catch {
      emitToast({ kind: "error", title: "Could not deactivate. Try again." });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleActivateConfirm() {
    if (!selected) return;
    setSubmitting(true);
    try {
      await activateShop(selected.id);
      emitToast({ kind: "success", title: `Shop '${selected.name}' activated.` });
      refresh();
      setActivateOpen(false);
      setSelected(null);
    } catch {
      emitToast({ kind: "error", title: "Could not activate. Try again." });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReconnectComplete(state: string) {
    if (!selected) return;
    try {
      await reconnectShop(selected.id, state);
      emitToast({ kind: "success", title: `Connection restored for '${selected.name}'.` });
      refresh();
      setReconnectOpen(false);
      setSelected(null);
    } catch {
      emitToast({ kind: "error", title: "Could not reconnect. Try again." });
    }
  }

  return (
    <>
      <CreateButtonBridge onOpen={handleOpenCreate} allocationAtLimit={allocation.at_limit} />

      <CreateShopModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          refresh();
        }}
        regions={regions}
      />

      <EditShopModal
        open={editOpen}
        shop={selected}
        regions={regions}
        onClose={() => {
          setEditOpen(false);
          setSelected(null);
        }}
        onUpdated={() => {
          setEditOpen(false);
          setSelected(null);
          refresh();
        }}
      />

      <ShopDetailsModal
        open={detailsOpen}
        shop={selected}
        onClose={() => {
          setDetailsOpen(false);
          setSelected(null);
        }}
        onEdit={() => {
          setDetailsOpen(false);
          setEditOpen(true);
        }}
        onActivate={() => {
          setDetailsOpen(false);
          setActivateOpen(true);
        }}
        onDeactivate={() => {
          setDetailsOpen(false);
          setDeactivateOpen(true);
        }}
        onReconnect={() => {
          setDetailsOpen(false);
          setReconnectOpen(true);
        }}
      />

      {/* Deactivate — amber confirm with slot-retention message (SHOP-17) */}
      <ConfirmModal
        open={deactivateOpen}
        variant="amber"
        title="Deactivate shop?"
        message={
          selected
            ? `'${selected.name}' will be hidden from the list. The allocated store slot remains used.`
            : ""
        }
        confirmLabel={submitting ? "Deactivating…" : "Deactivate"}
        onClose={() => {
          setDeactivateOpen(false);
          setSelected(null);
        }}
        onConfirm={() => void handleDeactivateConfirm()}
      />

      {/* Activate — blue confirm (SHOP-18) */}
      <ConfirmModal
        open={activateOpen}
        variant="blue"
        title="Activate shop?"
        message={selected ? `'${selected.name}' will appear as Active.` : ""}
        confirmLabel={submitting ? "Activating…" : "Activate"}
        onClose={() => {
          setActivateOpen(false);
          setSelected(null);
        }}
        onConfirm={() => void handleActivateConfirm()}
      />

      <RevealKeyModal
        open={revealOpen}
        shop={selected}
        onClose={() => {
          setRevealOpen(false);
          setSelected(null);
        }}
      />

      <RotateKeyModal
        open={rotateOpen}
        shop={selected}
        onClose={() => {
          setRotateOpen(false);
          setSelected(null);
        }}
        onRotated={() => {
          setRotateOpen(false);
          setSelected(null);
          refresh();
        }}
      />

      {/* Reconnect Google — reuses OAuthConnectionSection in a simple modal (SHOP-21) */}
      <Modal
        open={reconnectOpen}
        title="Reconnect Google Business Profile"
        subtitle={selected ? `Reconnect '${selected.name}' to your Google account.` : undefined}
        size="default"
        onClose={() => {
          setReconnectOpen(false);
          setSelected(null);
        }}
        footer={
          <button
            type="button"
            onClick={() => {
              setReconnectOpen(false);
              setSelected(null);
            }}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
        }
      >
        <div className="space-y-3">
          <p className="text-[13.5px] text-muted">
            Click below to reconnect via Google OAuth. The old token will be replaced.
          </p>
          <OAuthConnectionSection
            connected={null}
            onConnected={(d) => void handleReconnectComplete(d.state)}
            onError={() =>
              emitToast({ kind: "error", title: "Could not complete connection." })
            }
            onChangeConnection={() => {}}
          />
        </div>
      </Modal>
    </>
  );
}
