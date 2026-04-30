import { useState } from "react";
import { Modal } from "../modal/Modal";
import { ScopeSection } from "./ScopeSection";
import { updateTeamMember, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import type { RegionOption, ShopOption, TeamMemberRow } from "./types";

const inputCls =
  "w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputErrorCls =
  "w-full px-3 py-2 text-[14px] bg-white border border-red rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const inputLockedCls =
  "w-full px-3 py-2 text-[14px] bg-line-soft text-subtle border border-line rounded-md cursor-not-allowed";
const labelCls =
  "block text-[12px] font-semibold text-subtle tracking-[0.05em] uppercase mb-1";

interface EditTeamMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  member: TeamMemberRow;
  regions: RegionOption[];
  activeShops: ShopOption[];
}

interface FormErrors {
  full_name?: string;
  non_field_errors?: string;
  scope?: string;
}

function initialRegionIds(member: TeamMemberRow): Set<number> {
  return new Set(
    member.access_scopes
      .filter((s) => s.scope_type === "REGION" && s.region !== null)
      .map((s) => s.region as number),
  );
}

function initialShopIds(member: TeamMemberRow): Set<number> {
  return new Set(
    member.access_scopes
      .filter((s) => s.scope_type === "SHOP" && s.shop !== null)
      .map((s) => s.shop as number),
  );
}

export function EditTeamMemberModal({
  isOpen,
  onClose,
  member,
  regions,
  activeShops,
}: EditTeamMemberModalProps) {
  const [fullName, setFullName] = useState(member.full_name);
  const [role, setRole] = useState<"ORG_ADMIN" | "STAFF_ADMIN">(member.role);
  const [regionIds, setRegionIds] = useState<Set<number>>(() => initialRegionIds(member));
  const [shopIds, setShopIds] = useState<Set<number>>(() => initialShopIds(member));
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function handleClose() {
    onClose();
  }

  function validate(): FormErrors {
    const errs: FormErrors = {};
    if (!fullName.trim() || fullName.trim().length < 2 || fullName.trim().length > 100) {
      errs.full_name = "Full name must be between 2 and 100 characters.";
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
      await updateTeamMember(member.id, {
        full_name: fullName.trim(),
        role,
        region_ids: [...regionIds],
        shop_ids: [...shopIds],
      });
      emitToast({ kind: "success", title: "Team member updated." });
      window.dispatchEvent(new CustomEvent("team:member-updated"));
      onClose();
    } catch (err) {
      if (err instanceof ApiError && typeof err.data === "object" && err.data !== null) {
        const data = err.data as Record<string, unknown>;
        const fieldErrors: FormErrors = {};
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
      title="Edit Team Member"
      subtitle="Update the member's details and access."
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
            form="edit-team-member-form"
            disabled={submitting}
            className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[14px] font-semibold hover:bg-yellow-hover disabled:opacity-60"
          >
            {submitting ? "Saving…" : "Save Changes"}
          </button>
        </>
      }
    >
      <form id="edit-team-member-form" onSubmit={handleSubmit} className="space-y-4">
        {errors.non_field_errors && (
          <div
            className="rounded-md border p-2.5 text-[14px]"
            style={{
              backgroundColor: "#FEF2F2",
              borderColor: "rgba(220,38,38,0.3)",
              color: "#DC2626",
            }}
            role="alert"
            data-testid="non-field-error"
          >
            {errors.non_field_errors}
          </div>
        )}

        <div>
          <label htmlFor="etm-full-name" className={labelCls}>
            Full Name
          </label>
          <input
            id="etm-full-name"
            type="text"
            aria-label="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className={errors.full_name ? inputErrorCls : inputCls}
          />
          {errors.full_name && (
            <p role="alert" className="mt-1 text-[12px]" style={{ color: "#DC2626" }}>
              {errors.full_name}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="etm-email" className={labelCls}>
            Email
          </label>
          <input
            id="etm-email"
            type="email"
            aria-label="Email"
            value={member.email}
            readOnly
            aria-readonly="true"
            className={inputLockedCls}
          />
        </div>

        <div>
          <label htmlFor="etm-role" className={labelCls}>
            Role
          </label>
          <select
            id="etm-role"
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
            initialMode={initialShopIds(member).size > 0 ? "store" : "region"}
          />
        )}
      </form>
    </Modal>
  );
}
