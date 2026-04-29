import { useEffect, useState } from "react";
import { Modal } from "../modal/Modal";
import { ApiError, updateShop } from "./api";
import { emitToast } from "../../lib/toast";
import type { ShopRow, ShopUpdatePayload } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[13.5px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls = inputCls + " border-red";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface RegionLite {
  id: number;
  region_id: string;
  name: string;
}

interface Props {
  open: boolean;
  shop: ShopRow | null;
  onClose: () => void;
  onUpdated: (shop: ShopRow) => void;
  regions: RegionLite[];
}

export function EditShopModal({ open, shop, onClose, onUpdated, regions }: Props) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [region, setRegion] = useState<number | "">("");
  const [streetAddress, setStreetAddress] = useState("");
  const [errors, setErrors] = useState<Record<string, string | string[]>>({});
  const [submitting, setSubmitting] = useState(false);

  // Pre-fill fields when shop changes
  useEffect(() => {
    if (shop) {
      setName(shop.name);
      setPhone(shop.phone ?? "");
      setRegion(shop.region ?? "");
      setStreetAddress(shop.street_address ?? "");
      setErrors({});
      setSubmitting(false);
    }
  }, [shop]);

  function reset() {
    setName("");
    setPhone("");
    setRegion("");
    setStreetAddress("");
    setErrors({});
    setSubmitting(false);
  }

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
    const payload: ShopUpdatePayload = {
      name,
      phone,
      region: region === "" ? undefined : (region as number),
      street_address: streetAddress,
    };
    try {
      const updated = await updateShop(shop.id, payload);
      emitToast({ kind: "success", title: `Shop '${updated.name}' updated.` });
      onUpdated(updated);
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
        emitToast({
          kind: "error",
          title: "Something went wrong.",
          msg: "Please try again.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Edit Shop"
      subtitle="Update shop details."
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
            form="edit-shop-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting && (
              <span className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin" />
            )}
            Save Shop
          </button>
        </>
      }
    >
      <form id="edit-shop-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="es-name" className={labelCls}>
            Shop Name
          </label>
          <input
            id="es-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={fieldError("name") ? inputErrorCls : inputCls}
          />
          {fieldError("name") && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {fieldError("name")}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="es-region" className={labelCls}>
            Region
          </label>
          <select
            id="es-region"
            value={region === "" ? "" : String(region)}
            onChange={(e) => setRegion(e.target.value ? Number(e.target.value) : "")}
            className={fieldError("region") ? inputErrorCls : inputCls}
          >
            <option value="">Select region…</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.region_id})
              </option>
            ))}
          </select>
          {fieldError("region") && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {fieldError("region")}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="es-phone" className={labelCls}>
            Phone (optional)
          </label>
          <input
            id="es-phone"
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="es-street" className={labelCls}>
            Street Address
          </label>
          <input
            id="es-street"
            type="text"
            value={streetAddress}
            onChange={(e) => setStreetAddress(e.target.value)}
            className={inputCls}
          />
        </div>
      </form>
    </Modal>
  );
}
