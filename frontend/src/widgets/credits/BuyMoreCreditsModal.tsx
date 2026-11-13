import { Mail } from "lucide-react";
import { Modal } from "../modal/Modal";
import { buildCreditRequestMailto, type CreditRequestShop } from "./mailto";

export interface BuyMoreCreditsModalProps {
  open: boolean;
  onClose: () => void;
  organisationName: string;
  supportEmail: string;
  shop?: CreditRequestShop;
}

const ENABLED_COPY =
  "To purchase additional credits for this month, please contact your Review Bear administrator. Your administrator will add credits as soon as possible.";
const NOT_ENABLED_COPY =
  "AI replies aren't enabled for this shop yet. To turn them on, please contact your Review Bear administrator. Your administrator will add credits as soon as possible.";

/**
 * Shared Buy More Credits modal (CVIS-04, D-13..D-16). It only explains how to
 * contact the administrator and hands off to a mailto; there is no payment UI
 * and no role input — the recipient is always the platform support address.
 */
export function BuyMoreCreditsModal({
  open,
  onClose,
  organisationName,
  supportEmail,
  shop,
}: BuyMoreCreditsModalProps) {
  const href = buildCreditRequestMailto({ supportEmail, organisationName, shop });
  const copy = shop?.isEnabled === false ? NOT_ENABLED_COPY : ENABLED_COPY;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Buy More Credits"
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-white text-ink border border-line rounded-md text-[14px] font-normal hover:bg-line-soft"
          >
            Close
          </button>
          <a
            href={href}
            className="inline-flex items-center px-4 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[14px] font-semibold hover:bg-yellow-hover"
          >
            Contact Admin
          </a>
        </>
      }
    >
      <div className="flex gap-4">
        <div
          className="w-12 h-12 shrink-0 rounded-confirm-icon bg-blue-tint text-blue flex items-center justify-center"
          aria-hidden="true"
        >
          <Mail size={24} aria-hidden="true" />
        </div>
        <div>
          <p className="text-[14px] text-muted leading-[1.5]">{copy}</p>
          <p className="mt-2 text-[12px] text-muted leading-[1.5]">
            If your email app doesn&apos;t open, write to <span className="select-all">{supportEmail}</span>.
          </p>
        </div>
      </div>
    </Modal>
  );
}
