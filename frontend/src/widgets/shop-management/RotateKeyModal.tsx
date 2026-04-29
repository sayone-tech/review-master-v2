import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Modal } from "../modal/Modal";
import { ApiError, rotateKey } from "./api";
import { emitToast } from "../../lib/toast";
import type { ShopRow } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface Props {
  open: boolean;
  shop: ShopRow | null;
  onClose: () => void;
  onRotated: (shop: ShopRow) => void;
}

export function RotateKeyModal({ open, shop, onClose, onRotated }: Props) {
  const [newApiKey, setNewApiKey] = useState("");
  const [visible, setVisible] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setNewApiKey("");
    setVisible(false);
    setErrors({});
    setSubmitting(false);
  }

  useEffect(() => {
    if (!open) reset();
  }, [open]);

  function handleClose() {
    reset();
    onClose();
  }

  function fieldError(key: string): string | undefined {
    const e = errors[key];
    if (!e) return undefined;
    return Array.isArray(e) ? e[0] : String(e);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!shop) return;
    setErrors({});
    setSubmitting(true);
    try {
      const updated = await rotateKey(shop.id, { new_api_key: newApiKey });
      emitToast({ kind: "success", title: `API key rotated for '${shop.name}'.` });
      onRotated(updated);
      reset();
      onClose();
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 400 &&
        err.data &&
        typeof err.data === "object"
      ) {
        setErrors(err.data as Record<string, string | string[]>);
      } else {
        emitToast({ kind: "error", title: "Something went wrong.", msg: "Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const nonField = errors.non_field_errors;

  return (
    <Modal
      open={open}
      title="Rotate API Key"
      subtitle={shop ? `Replace the API key for '${shop.name}'.` : undefined}
      size="default"
      onClose={handleClose}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-normal hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="rotate-key-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting ? "Rotating…" : "Rotate Key"}
          </button>
        </>
      }
    >
      <form id="rotate-key-form" onSubmit={handleSubmit} className="space-y-4">
        {nonField && (
          <div
            className="rounded-md border p-2.5 text-[13px]"
            style={{
              backgroundColor: "#FEF2F2",
              borderColor: "rgba(220,38,38,0.3)",
              color: "#DC2626",
            }}
            role="alert"
            data-testid="rotate-non-field-error"
          >
            {Array.isArray(nonField) ? nonField[0] : nonField}
          </div>
        )}
        <div>
          <label htmlFor="rk-new-key" className={labelCls}>
            New API Key
          </label>
          <div className="relative">
            <input
              id="rk-new-key"
              type={visible ? "text" : "password"}
              value={newApiKey}
              onChange={(e) => setNewApiKey(e.target.value)}
              className={fieldError("new_api_key") ? inputErrorCls : inputCls}
              autoFocus
            />
            <button
              type="button"
              onClick={() => setVisible(!visible)}
              aria-label={visible ? "Hide" : "Show"}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted"
            >
              {visible ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          {fieldError("new_api_key") && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {fieldError("new_api_key")}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
