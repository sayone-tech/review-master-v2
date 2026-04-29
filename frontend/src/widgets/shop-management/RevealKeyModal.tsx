import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Modal } from "../modal/Modal";
import { revealKey } from "./api";
import { emitToast } from "../../lib/toast";
import type { ShopRow } from "./types";

type Phase = "confirm" | "revealed" | "expired";

interface Props {
  open: boolean;
  shop: ShopRow | null;
  onClose: () => void;
}

export function RevealKeyModal({ open, shop, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("confirm");
  const [key, setKey] = useState<string>("");
  const [secondsLeft, setSecondsLeft] = useState(30);

  useEffect(() => {
    if (!open) {
      setPhase("confirm");
      setKey("");
      setSecondsLeft(30);
    }
  }, [open]);

  // 30-second countdown timer once key is revealed
  useEffect(() => {
    if (phase !== "revealed") return;
    const t = window.setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          window.clearInterval(t);
          setPhase("expired");
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(t);
  }, [phase]);

  async function handleConfirm() {
    if (!shop) return;
    try {
      const r = await revealKey(shop.id);
      setKey(r.api_key);
      setPhase("revealed");
      setSecondsLeft(30);
    } catch {
      emitToast({ kind: "error", title: "Could not reveal key. Please try again." });
    }
  }

  function handleClose() {
    setPhase("confirm");
    setKey("");
    setSecondsLeft(30);
    onClose();
  }

  // Confirm phase: amber warning before revealing
  if (phase === "confirm") {
    return (
      <Modal
        open={open}
        onClose={handleClose}
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={handleClose}
              className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
              data-testid="reveal-cancel"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleConfirm()}
              className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
              data-testid="reveal-confirm"
            >
              Reveal Key
            </button>
          </>
        }
      >
        <div className="flex gap-3.5">
          <div
            className="w-11 h-11 shrink-0 rounded-confirm-icon flex items-center justify-center bg-amber-tint text-amber"
            aria-hidden="true"
          >
            <AlertTriangle size={22} />
          </div>
          <div>
            <h3 className="text-[18px] font-semibold text-ink mb-1.5">Reveal API key?</h3>
            <p className="text-[13.5px] text-muted leading-[1.5]">
              The decrypted API key will be shown for 30 seconds. This action is logged in the
              audit trail.
            </p>
          </div>
        </div>
      </Modal>
    );
  }

  // Revealed phase: show the key with countdown
  if (phase === "revealed") {
    return (
      <Modal
        open={open}
        title="API Key"
        subtitle={`Hidden automatically in ${secondsLeft}s`}
        size="default"
        onClose={handleClose}
        footer={
          <button
            type="button"
            onClick={handleClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Close
          </button>
        }
      >
        <div className="space-y-3">
          <div
            className="rounded-md border p-3"
            style={{ backgroundColor: "#F9FAFB", borderColor: "#E5E7EB" }}
          >
            <code
              className="font-mono text-[13px] break-all"
              data-testid="revealed-key"
            >
              {key}
            </code>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="h-1 rounded-full flex-1 overflow-hidden"
              style={{ backgroundColor: "#E5E7EB" }}
            >
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${(secondsLeft / 30) * 100}%`,
                  backgroundColor: secondsLeft > 10 ? "#16A34A" : "#D97706",
                }}
              />
            </div>
            <span className="text-[12px] text-muted tabular-nums">{secondsLeft}s</span>
          </div>
          <p className="text-[12px] text-muted">
            Copy this key now. It will be hidden after the countdown.
          </p>
        </div>
      </Modal>
    );
  }

  // Expired phase: key has been masked again
  return (
    <Modal
      open={open}
      title="API Key Hidden"
      size="sm"
      onClose={handleClose}
      footer={
        <>
          <button
            type="button"
            onClick={() => {
              setPhase("confirm");
              setKey("");
              setSecondsLeft(30);
            }}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Show Again
          </button>
          <button
            type="button"
            onClick={handleClose}
            className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover"
          >
            Close
          </button>
        </>
      }
    >
      <p className="text-[13.5px] text-muted">
        The key has been hidden.{" "}
        {shop?.api_key_masked && (
          <code className="font-mono text-[12.5px]">{shop.api_key_masked}</code>
        )}{" "}
        Click &ldquo;Show Again&rdquo; to reveal it once more.
      </p>
    </Modal>
  );
}
