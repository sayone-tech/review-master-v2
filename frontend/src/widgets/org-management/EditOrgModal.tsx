import { useEffect, useState } from "react";
import { Modal } from "../modal";
import { updateOrg, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { OrgRow, OrgType, UpdateOrgPayload } from "./types";
import { ToggleSwitch } from "./ToggleSwitch";
import { computeCreditHint, parseCreditInput } from "./creditHint";

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
  const [allowCustomSyncDepth, setAllowCustomSyncDepth] = useState(false);
  const [credits, setCredits] = useState("0");
  // Value captured when the modal opened: the allocation is sent only when the
  // typed value differs, so a stale form can never silently revert another
  // admin's change (T-32-09).
  const [openedCredits, setOpenedCredits] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (org) {
      setName(org.name);
      setOrgType(org.org_type);
      setStores(String(org.number_of_stores));
      setAddress(org.address ?? "");
      setAllowCustomSyncDepth(org.allow_custom_sync_depth ?? false);
      setCredits(String(org.monthly_credit_allocation));
      setOpenedCredits(org.monthly_credit_allocation);
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
    if (parseCreditInput(credits) === null)
      e.monthly_credit_allocation = "Enter a whole number between 0 and 10,000.";
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
      allow_custom_sync_depth: allowCustomSyncDepth,
    };
    const parsedCredits = parseCreditInput(credits);
    if (parsedCredits !== null && parsedCredits !== openedCredits)
      payload.monthly_credit_allocation = parsedCredits;
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

  const creditHint = computeCreditHint({
    mode: "edit",
    saved: currentOrg.monthly_credit_allocation,
    thisMonth: currentOrg.current_month_credit_allocation,
    typed: credits,
    nowUtc: new Date(),
  });
  const creditHintDeferred =
    creditHint.kind === "deferred" || creditHint.kind === "deferred-off";

  const inputBase =
    "w-full px-3 py-2 text-[14px] bg-white border rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";

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
            className="inline-flex items-center px-4 py-2 bg-white text-ink border border-line rounded-md text-[14px] font-normal hover:bg-line-soft"
            data-testid="edit-discard"
          >
            Discard Changes
          </button>
          <button
            type="submit"
            form="edit-org-form"
            disabled={submitting}
            className="inline-flex items-center gap-2 px-4 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[14px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
            data-testid="edit-submit"
          >
            {submitting && (
              <span
                className="w-4 h-4 border-2 border-black/20 border-t-black rounded-full animate-spin"
                aria-hidden="true"
              />
            )}
            Save Changes
          </button>
        </>
      }
    >
      <form id="edit-org-form" onSubmit={submit} noValidate className="space-y-4">
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
          <label
            htmlFor="edit-org-credits"
            className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1"
          >
            Monthly credits per shop
          </label>
          <input
            id="edit-org-credits"
            type="number"
            min={0}
            max={10000}
            step={1}
            inputMode="numeric"
            value={credits}
            onChange={(e) => setCredits(e.target.value)}
            aria-describedby="edit-org-credits-help"
            className={`${inputBase} ${errors.monthly_credit_allocation ? "border-red" : "border-line"}`}
            data-testid="edit-field-monthly_credit_allocation"
          />
          {errors.monthly_credit_allocation && (
            <p className="mt-1 text-[12px] text-red" role="alert">
              {errors.monthly_credit_allocation}
            </p>
          )}
          <div id="edit-org-credits-help">
            <p className="mt-1 text-[12px] text-muted">
              Each shop in this organisation gets this many credits at the start of
              every month. Unused credits lapse.
            </p>
            <p
              data-testid="credit-allocation-hint"
              role="status"
              aria-live="polite"
              className={
                creditHint.kind === "hidden"
                  ? undefined
                  : creditHintDeferred
                    ? "mt-2 bg-amber-tint text-[#92400E] px-4 py-2 rounded-md text-[12px]"
                    : "mt-1 text-[12px] text-muted"
              }
            >
              {creditHint.text}
            </p>
          </div>
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
        <div className="mt-4">
          <ToggleSwitch
            id="edit-allow_custom_sync_depth"
            checked={allowCustomSyncDepth}
            onChange={(v) => setAllowCustomSyncDepth(v)}
            label="Allow configurable sync depth"
            description="When enabled, Org Admins can choose how far back to sync reviews when adding a new shop."
          />
        </div>
      </form>
    </Modal>
  );
}
