import { useState } from "react";
import { Modal } from "../modal/Modal";
import { ScopeSection } from "./ScopeSection";
import { createTeamMember, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionOption, ShopOption } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls =
  "w-full px-3 py-2 text-[14px] bg-white border border-red rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface AddTeamMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  regions: RegionOption[];
  activeShops: ShopOption[];
}

interface FormErrors {
  full_name?: string;
  email?: string;
  non_field_errors?: string;
  scope?: string;
}

export function AddTeamMemberModal({
  isOpen,
  onClose,
  regions,
  activeShops,
}: AddTeamMemberModalProps) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"ORG_ADMIN" | "STAFF_ADMIN">("ORG_ADMIN");
  const [regionIds, setRegionIds] = useState<Set<number>>(new Set());
  const [shopIds, setShopIds] = useState<Set<number>>(new Set());
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setFullName("");
    setEmail("");
    setRole("ORG_ADMIN");
    setRegionIds(new Set());
    setShopIds(new Set());
    setErrors({});
    setSubmitting(false);
  }

  function handleClose() {
    reset();
    onClose();
  }

  function validate(): FormErrors {
    const errs: FormErrors = {};
    if (!fullName.trim() || fullName.trim().length < 2 || fullName.trim().length > 100) {
      errs.full_name = "Full name must be between 2 and 100 characters.";
    }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = "Please enter a valid email address.";
    }
    if (role === "STAFF_ADMIN" && regionIds.size === 0 && shopIds.size === 0) {
      errs.scope = "Please select at least one region or store.";
    }
    return errs;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      await createTeamMember({
        full_name: fullName.trim(),
        email: email.trim(),
        invited_for_role: role,
        region_ids: [...regionIds],
        shop_ids: [...shopIds],
      });
      emitToast({ kind: "success", title: `Invitation sent to ${email.trim()}.` });
      window.dispatchEvent(new CustomEvent("team:member-added"));
      reset();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && typeof err.data === "object" && err.data !== null) {
        const data = err.data as Record<string, unknown>;
        const fieldErrors: FormErrors = {};
        if (data.email) {
          const emailErr = data.email;
          fieldErrors.email = Array.isArray(emailErr) ? String(emailErr[0]) : String(emailErr);
        }
        if (data.non_field_errors) {
          const nfe = data.non_field_errors;
          fieldErrors.non_field_errors = Array.isArray(nfe) ? String(nfe[0]) : String(nfe);
        }
        if (data.full_name) {
          const fnErr = data.full_name;
          fieldErrors.full_name = Array.isArray(fnErr) ? String(fnErr[0]) : String(fnErr);
        }
        setErrors(fieldErrors);
      } else {
        emitToast({ kind: "error", title: "Something went wrong.", msg: "Please try again." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="Add Team Member"
      subtitle="Invite a new member to your team."
      size="default"
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            className="inline-flex items-center px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[14px] font-normal hover:bg-line-soft"
          >
            Discard
          </button>
          <button
            type="submit"
            form="add-team-member-form"
            disabled={submitting}
            className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[14px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting ? "Sending…" : "Send Invitation"}
          </button>
        </>
      }
    >
      <form id="add-team-member-form" onSubmit={handleSubmit} className="space-y-4">
        {(errors.non_field_errors ?? errors.full_name ?? errors.email ?? errors.scope) && (
          <div
            className="rounded-md border p-2.5 text-[14px]"
            style={{
              backgroundColor: "#FEF2F2",
              borderColor: "rgba(220,38,38,0.3)",
              color: "#DC2626",
            }}
            role="alert"
            data-testid="form-errors"
          >
            {errors.non_field_errors
              ? errors.non_field_errors
              : "Please fix the errors below."}
          </div>
        )}

        <div>
          <label htmlFor="atm-full-name" className={labelCls}>
            Full Name
          </label>
          <input
            id="atm-full-name"
            type="text"
            aria-label="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={errors.full_name ? inputErrorCls : inputCls}
          />
          {errors.full_name && (
            <p id="atm-full-name-error" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {errors.full_name}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="atm-email" className={labelCls}>
            Email
          </label>
          <input
            id="atm-email"
            type="email"
            aria-label="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={errors.email ? inputErrorCls : inputCls}
          />
          {errors.email && (
            <p id="atm-email-error" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {errors.email}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="atm-role" className={labelCls}>
            Role
          </label>
          <select
            id="atm-role"
            aria-label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as "ORG_ADMIN" | "STAFF_ADMIN")}
            className={inputCls}
          >
            <option value="ORG_ADMIN">Manager</option>
            <option value="STAFF_ADMIN">Staff</option>
          </select>
        </div>

        {role === "STAFF_ADMIN" && (
          <ScopeSection
            regions={regions}
            activeShops={activeShops}
            selectedRegionIds={regionIds}
            selectedShopIds={shopIds}
            onChangeRegions={setRegionIds}
            onChangeShops={setShopIds}
            validationError={errors.scope}
          />
        )}
      </form>
    </Modal>
  );
}
