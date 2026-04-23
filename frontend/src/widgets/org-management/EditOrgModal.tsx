import { useEffect, useState } from "react";
import { Modal } from "../modal";
import { updateOrg, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow, OrgType, UpdateOrgPayload } from "./types";

const ORG_TYPE_OPTIONS: { value: OrgType; label: string }[] = [
  { value: "RETAIL", label: "Retail" },
  { value: "RESTAURANT", label: "Restaurant" },
  { value: "PHARMACY", label: "Pharmacy" },
  { value: "SUPERMARKET", label: "Supermarket" },
];

interface Props {
  org: OrgRow | null;
  onClose: () => void;
  onUpdated: () => void | Promise<void>;
}

export function EditOrgModal({ org, onClose, onUpdated }: Props) {
  const [name, setName] = useState("");
  const [orgType, setOrgType] = useState<OrgType>("RETAIL");
  const [stores, setStores] = useState("");
  const [address, setAddress] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (org) {
      setName(org.name);
      setOrgType(org.org_type);
      setStores(String(org.number_of_stores));
      setAddress(org.address ?? "");
      setErrors({});
    }
  }, [org]);

  if (!org) return null;

  // org is non-null from this point — captured in the closure below
  const currentOrg = org;

  function validate(): Record<string, string> {
    const e: Record<string, string> = {};
    if (name.trim().length < 2 || name.trim().length > 100)
      e.name = "Name must be 2–100 characters.";
    const n = Number(stores);
    if (!Number.isInteger(n) || n < 1 || n > 1000)
      e.number_of_stores = "Enter a whole number between 1 and 1000.";
    if (address.length > 500) e.address = "Address must be 500 characters or fewer.";
    return e;
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length > 0) return;
    setSubmitting(true);
    const payload: UpdateOrgPayload = {
      name: name.trim(),
      org_type: orgType,
      number_of_stores: Number(stores),
      address: address.trim(),
    };
    try {
      await updateOrg(currentOrg.id, payload);
      emitToast({ kind: "success", title: "Organisation updated." });
      await onUpdated();
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldErrs: Record<string, string> = {};
        for (const [k, v] of Object.entries(err.fieldErrors))
          fieldErrs[k] = Array.isArray(v) ? v[0] : String(v);
        setErrors(fieldErrs);
      } else {
        emitToast({
          kind: "error",
          title: "Something went wrong.",
          msg: "Please try again. If the problem persists, contact support.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  const inputBase =
    "w-full px-3 py-2 text-[13.5px] bg-white border rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

  return (
    <Modal
      open={true}
      onClose={onClose}
      title="Edit Organisation"
      size="default"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            data-testid="edit-discard"
          >
            Discard Changes
          </button>
          <button
            type="submit"
            form="edit-org-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-60"
            data-testid="edit-submit"
          >
            {submitting && (
              <span
                className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin"
                aria-hidden="true"
              />
            )}
            Save Changes
          </button>
        </>
      }
    >
      <form id="edit-org-form" onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1">
            Organisation Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className={`${inputBase} ${errors.name ? "border-red" : "border-line"}`}
            data-testid="edit-field-name"
          />
          {errors.name && (
            <p className="mt-1 text-[12px] text-red" role="alert">
              {errors.name}
            </p>
          )}
        </div>
        <div>
          <label className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1">
            Organisation Type
          </label>
          <select
            value={orgType}
            onChange={(e) => setOrgType(e.target.value as OrgType)}
            className={`${inputBase} ${errors.org_type ? "border-red" : "border-line"}`}
            data-testid="edit-field-org_type"
          >
            {ORG_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1">
            Email
          </label>
          <input
            type="email"
            value={currentOrg.email}
            disabled
            className={`${inputBase} bg-line-soft text-subtle cursor-not-allowed`}
            data-testid="edit-field-email"
          />
          <p className="mt-1 text-[12px] text-muted">
            Email cannot be changed after creation.
          </p>
        </div>
        <div>
          <label className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1">
            Number of Stores
          </label>
          <input
            type="number"
            min={1}
            max={1000}
            value={stores}
            onChange={(e) => setStores(e.target.value)}
            required
            className={`${inputBase} ${errors.number_of_stores ? "border-red" : "border-line"}`}
            data-testid="edit-field-number_of_stores"
          />
          {errors.number_of_stores && (
            <p className="mt-1 text-[12px] text-red" role="alert">
              {errors.number_of_stores}
            </p>
          )}
        </div>
        <div>
          <label className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1">
            Address{" "}
            <span className="text-faint font-normal normal-case">(optional)</span>
          </label>
          <textarea
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            rows={3}
            maxLength={500}
            className={`${inputBase} ${errors.address ? "border-red" : "border-line"}`}
            data-testid="edit-field-address"
          />
          {errors.address && (
            <p className="mt-1 text-[12px] text-red" role="alert">
              {errors.address}
            </p>
          )}
        </div>
      </form>
    </Modal>
  );
}
