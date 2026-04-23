import { useState } from "react";
import { Modal } from "../modal";
import { createOrg, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { CreateOrgPayload, OrgType } from "./types";

const ORG_TYPE_OPTIONS: { value: OrgType | ""; label: string }[] = [
  { value: "", label: "Select a type" },
  { value: "RETAIL", label: "Retail" },
  { value: "RESTAURANT", label: "Restaurant" },
  { value: "PHARMACY", label: "Pharmacy" },
  { value: "SUPERMARKET", label: "Supermarket" },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void | Promise<void>;
}

export function CreateOrgModal({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [orgType, setOrgType] = useState<OrgType | "">("");
  const [email, setEmail] = useState("");
  const [stores, setStores] = useState("");
  const [address, setAddress] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setName("");
    setOrgType("");
    setEmail("");
    setStores("");
    setAddress("");
    setErrors({});
  };

  function validate(): Record<string, string> {
    const e: Record<string, string> = {};
    if (name.trim().length < 2 || name.trim().length > 100)
      e.name = "Name must be 2–100 characters.";
    if (!orgType) e.org_type = "Please select a type.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
      e.email = "Enter a valid email address.";
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
    const payload: CreateOrgPayload = {
      name: name.trim(),
      org_type: orgType as OrgType,
      email: email.trim(),
      address: address.trim(),
      number_of_stores: Number(stores),
    };
    try {
      await createOrg(payload);
      emitToast({
        kind: "success",
        title: `Organisation created. Invitation email sent to ${payload.email}.`,
      });
      reset();
      await onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldErrs: Record<string, string> = {};
        for (const [k, v] of Object.entries(err.fieldErrors)) {
          fieldErrs[k] = Array.isArray(v) ? v[0] : String(v);
        }
        // Override email duplicate message to exact UI copy:
        if (fieldErrs.email)
          fieldErrs.email = "An organisation with this email already exists.";
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

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Create Organisation"
      subtitle="Fill in the details below. An invitation email will be sent on save."
      size="default"
      footer={
        <>
          <button
            type="button"
            onClick={() => {
              reset();
              onClose();
            }}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
            data-testid="create-discard"
          >
            Discard
          </button>
          <button
            type="submit"
            form="create-org-form"
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-60"
            data-testid="create-submit"
          >
            {submitting && (
              <span
                className="w-3.5 h-3.5 border-2 border-black/20 border-t-black rounded-full animate-spin"
                aria-hidden="true"
              />
            )}
            Create Organisation
          </button>
        </>
      }
    >
      <form id="create-org-form" onSubmit={submit} className="space-y-4">
        <Field label="Organisation Name" id="new-org-name" error={errors.name}>
          <input
            id="new-org-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Acme Retail Group"
            required
            className={inputCls(!!errors.name)}
            data-testid="field-name"
          />
        </Field>
        <Field
          label="Organisation Type"
          id="new-org-type"
          error={errors.org_type}
        >
          <select
            id="new-org-type"
            value={orgType}
            onChange={(e) => setOrgType(e.target.value as OrgType | "")}
            required
            className={inputCls(!!errors.org_type)}
            data-testid="field-org_type"
          >
            {ORG_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Email" id="new-org-email" error={errors.email}>
          <input
            id="new-org-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@example.com"
            required
            className={inputCls(!!errors.email)}
            data-testid="field-email"
          />
        </Field>
        <Field
          label="Number of Stores"
          id="new-org-stores"
          error={errors.number_of_stores}
        >
          <input
            id="new-org-stores"
            type="number"
            min={1}
            max={1000}
            value={stores}
            onChange={(e) => setStores(e.target.value)}
            placeholder="e.g. 5"
            required
            className={inputCls(!!errors.number_of_stores)}
            data-testid="field-number_of_stores"
          />
        </Field>
        <Field
          label="Address"
          id="new-org-address"
          error={errors.address}
          optional
        >
          <textarea
            id="new-org-address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder="Full address (optional)"
            className={inputCls(!!errors.address)}
            data-testid="field-address"
          />
        </Field>
      </form>
    </Modal>
  );
}

function inputCls(hasError: boolean) {
  const base =
    "w-full px-3 py-2 text-[13.5px] bg-white border rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
  return hasError ? `${base} border-red` : `${base} border-line`;
}

function Field({
  label,
  id,
  error,
  optional = false,
  children,
}: {
  label: string;
  id: string;
  error?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1"
      >
        {label}
        {optional && (
          <span className="text-faint font-normal normal-case"> (optional)</span>
        )}
      </label>
      {children}
      {error && (
        <p
          className="mt-1 text-[12px] text-red"
          role="alert"
          data-testid={`error-${id}`}
        >
          {error}
        </p>
      )}
    </div>
  );
}
