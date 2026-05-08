// Phase 13 Plan 07 — ActionItemCreateModal (manual creation, ACTN-09).
//
// Form fields per UI-SPEC §3:
//   Title (5-200), Scope, Shop (req when SHOP, hidden when BRAND),
//   Priority (default Medium), Assignee (optional), Due Date (today+),
//   Initial note (optional, 1-2000).
//
// ACTN-09 enforcement:
//   The Brand <option> in the scope <select> is rendered ONLY when
//   userRole === "ORG_ADMIN" (and "SUPERADMIN"). Staff cannot select Brand.
//   Staff can still create shop-scoped items; the shop dropdown for Staff is
//   filtered server-side via list_action_items selector + StaffAccessScope.
//
// On submit: POST /api/v1/action-items/ via createActionItemBackend (sends
// shop= and assignee= keys matching the DRF serializer field names).
import { useEffect, useState } from "react";
import { Modal } from "../modal/Modal";
import { createActionItemBackend, ApiError } from "./api";
import { emitToast } from "../../lib/toast";
import { getAssignableMembers } from "./assigneeUtils";
import type {
  ActionItemPriority,
  ActionItemScope,
  ShopOption,
  TeamMember,
  UserRole,
} from "./types";

interface Props {
  open: boolean;
  userRole: UserRole;
  shops: ShopOption[];
  teamMembers: TeamMember[];
  onClose: () => void;
  onCreated: () => void;
}

export function ActionItemCreateModal({
  open,
  userRole,
  shops,
  teamMembers,
  onClose,
  onCreated,
}: Props) {
  const today = new Date().toISOString().slice(0, 10);
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState<ActionItemScope>("SHOP");
  const [shopId, setShopId] = useState<number | "">("");
  const [priority, setPriority] = useState<ActionItemPriority>("MEDIUM");
  const [assigneeId, setAssigneeId] = useState<number | "">("");
  const [dueDate, setDueDate] = useState("");
  const [initialNote, setInitialNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state on open transitions.
  useEffect(() => {
    if (!open) return;
    setTitle("");
    setScope("SHOP");
    setShopId("");
    setPriority("MEDIUM");
    setAssigneeId("");
    setDueDate("");
    setInitialNote("");
    setError(null);
  }, [open]);

  // Clear shop when switching to BRAND scope.
  useEffect(() => {
    if (scope === "BRAND") setShopId("");
  }, [scope]);

  if (!open) return null;

  const titleLen = title.trim().length;
  const titleValid = titleLen >= 5 && titleLen <= 200;
  const shopValid = scope === "BRAND" || shopId !== "";
  const noteValid = initialNote.length <= 2000;
  const formValid = titleValid && shopValid && noteValid && !submitting;

  const handleSubmit = async () => {
    if (!formValid) return;
    setSubmitting(true);
    setError(null);
    try {
      await createActionItemBackend({
        title: title.trim(),
        scope,
        priority,
        shop: scope === "SHOP" && shopId !== "" ? Number(shopId) : null,
        assignee: assigneeId !== "" ? Number(assigneeId) : null,
        due_date: dueDate || null,
        initial_note: initialNote.trim() || undefined,
      });
      emitToast({ kind: "success", title: "Action item created" });
      onCreated();
    } catch (e) {
      let message = "Something went wrong. Please try again.";
      if (e instanceof ApiError && e.data && typeof e.data === "object") {
        const data = e.data as Record<string, unknown>;
        const firstKey = Object.keys(data)[0];
        if (firstKey) {
          const v = data[firstKey];
          if (Array.isArray(v) && v.length > 0) message = `${firstKey}: ${String(v[0])}`;
          else if (typeof v === "string") message = `${firstKey}: ${v}`;
        }
      }
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const showBrandOption = userRole === "ORG_ADMIN" || userRole === "SUPERADMIN";

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="default"
      title="New Action Item"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-[14px] bg-white border border-line rounded-md hover:bg-line-soft disabled:opacity-50"
          >
            Discard
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!formValid}
            className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Title
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
            maxLength={200}
            disabled={submitting}
          />
          <span className="text-[12px] text-muted text-right block mt-1">
            {titleLen} / 200 (min 5)
          </span>
        </label>

        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Scope
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as ActionItemScope)}
            className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
            disabled={submitting}
          >
            <option value="SHOP">Shop</option>
            {/* ACTN-09: Brand option hidden from Staff. */}
            {showBrandOption && <option value="BRAND">Brand</option>}
          </select>
        </label>

        {scope === "SHOP" && (
          <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
            Shop
            <select
              value={shopId}
              onChange={(e) => setShopId(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
              disabled={submitting}
            >
              <option value="">Select a shop…</option>
              {shops.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {!shopValid && scope === "SHOP" && shopId === "" && (
              <span className="text-[12px] text-red mt-1 block">
                Shop is required for shop-scoped items.
              </span>
            )}
          </label>
        )}

        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Priority
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as ActionItemPriority)}
            className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
            disabled={submitting}
          >
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </label>

        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Assignee
          <span className="ml-2 normal-case font-normal text-[11px] text-subtle">
            {scope === "BRAND" ? "(org admins only)" : "(org admins + assigned staff)"}
          </span>
          <select
            value={assigneeId}
            onChange={(e) => setAssigneeId(e.target.value ? Number(e.target.value) : "")}
            className="mt-1 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
            disabled={submitting}
          >
            <option value="">Unassigned</option>
            {getAssignableMembers(teamMembers, scope, shopId !== "" ? Number(shopId) : null).map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Due date
          <input
            type="date"
            value={dueDate}
            min={today}
            onChange={(e) => setDueDate(e.target.value)}
            className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
            disabled={submitting}
          />
        </label>

        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Initial note (optional)
          <textarea
            value={initialNote}
            onChange={(e) => setInitialNote(e.target.value)}
            className="mt-1 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md resize-none h-[80px] focus:outline-none focus:ring-2 focus:ring-yellow"
            maxLength={2000}
            disabled={submitting}
          />
          <span className="text-[12px] text-muted text-right block mt-1">
            {initialNote.length} / 2000
          </span>
        </label>

        {error && (
          <p className="text-[12px] text-red" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
