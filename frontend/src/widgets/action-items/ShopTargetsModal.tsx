import { useState } from "react";
import { Modal } from "../modal/Modal";
import { SetTargetModal } from "../shop-management/SetTargetModal";
import { TargetsTab } from "../shop-management/TargetsTab";
import { useTargets } from "../shop-management/useTargets";

interface Props {
  open: boolean;
  shopId: number | null;
  shopName: string;
  isOrgAdmin: boolean;
  onClose: () => void;
}

export function ShopTargetsModal({ open, shopId, shopName, isOrgAdmin, onClose }: Props) {
  const [showSetTarget, setShowSetTarget] = useState(false);
  const targets = useTargets(shopId);

  return (
    <>
      <Modal
        open={open}
        title={`Review Targets — ${shopName}`}
        size="lg"
        onClose={onClose}
        footer={
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
          >
            Close
          </button>
        }
      >
        {shopId !== null ? (
          <TargetsTab
            shopId={shopId}
            isOrgAdmin={isOrgAdmin}
            targets={targets}
            onAddTarget={() => setShowSetTarget(true)}
          />
        ) : null}
      </Modal>

      {shopId !== null && (
        <SetTargetModal
          open={showSetTarget}
          shopId={shopId}
          existingTargets={targets.rows}
          onSave={targets.addTarget}
          onClose={() => setShowSetTarget(false)}
        />
      )}
    </>
  );
}
