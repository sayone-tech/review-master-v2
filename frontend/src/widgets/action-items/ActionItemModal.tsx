// Phase 13 Plan 07 — ActionItemModal (3 tabs: Details / Notes / Source Review).
//
// ACTN-06: 3-tab modal; Source Review tab visible only when source=AI.
// ACTN-07: Title / Priority / Due Date / Assignee editable in Edit mode.
//          Scope and Shop are NOT editable for either AI or manual items
//          (CONTEXT.md decision).
// ACTN-08: Status dropdown at top of Details tab — immediate transition on
//          change via POST /transition-status/.
// ACTN-10: Notes tab is append-only (rendering owned by NotesTab).
// ACTN-11: Source Review tab includes "Open in Reviews" deep link.
import { useEffect, useState } from "react";
import { Modal } from "../modal/Modal";
import { NotesTab } from "./NotesTab";
import { PriorityIndicator } from "./PriorityIndicator";
import { SourceReviewTab } from "./SourceReviewTab";
import { addNote, getActionItem, transitionStatus, updateActionItemBackend } from "./api";
import { emitToast } from "../../lib/toast";
import {
  STATUS_LABEL,
  type ActionItemDetail,
  type ActionItemPriority,
  type ActionItemStatus,
  type ShopOption,
  type TeamMember,
} from "./types";

type EditDraft = {
  title: string;
  priority: ActionItemPriority;
  due_date: string;
  assignee_id: number | null;
};

type TabId = "details" | "notes" | "source";

interface Props {
  open: boolean;
  itemId: number | null;
  shops: ShopOption[];
  teamMembers: TeamMember[];
  onClose: () => void;
  onChanged: () => void;
}

interface TabBarProps {
  tabs: { id: TabId; label: string }[];
  active: TabId;
  onChange: (id: TabId) => void;
}

function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <div role="tablist" className="flex border-b border-line gap-0 px-0">
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={`px-4 py-2 text-[14px] font-semibold transition-colors ${
              isActive
                ? "text-ink border-b-2 border-yellow -mb-px"
                : "text-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

interface DetailsTabProps {
  item: ActionItemDetail;
  editing: boolean;
  draft: EditDraft;
  setDraft: (d: EditDraft) => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: () => void;
  onStatusChange: (s: ActionItemStatus) => void;
  saving: boolean;
  error: string | null;
  teamMembers: TeamMember[];
}

function DetailsTab({
  item,
  editing,
  draft,
  setDraft,
  onEdit,
  onCancelEdit,
  onSave,
  onStatusChange,
  saving,
  error,
  teamMembers,
}: DetailsTabProps) {
  const today = new Date().toISOString().slice(0, 10);
  if (!editing) {
    return (
      <div className="p-4 space-y-4" role="tabpanel">
        <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
          Status
          <select
            value={item.status}
            onChange={(e) => onStatusChange(e.target.value as ActionItemStatus)}
            className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          >
            <option value="TODO">{STATUS_LABEL.TODO}</option>
            <option value="IN_PROGRESS">{STATUS_LABEL.IN_PROGRESS}</option>
            <option value="COMPLETE">{STATUS_LABEL.COMPLETE}</option>
            <option value="WONT_DO">{STATUS_LABEL.WONT_DO}</option>
          </select>
        </label>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-4 text-[14px]">
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Title
            </dt>
            <dd className="text-ink mt-1">{item.title}</dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Priority
            </dt>
            <dd className="mt-1">
              <PriorityIndicator priority={item.priority} />
            </dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Due date
            </dt>
            <dd className="text-ink mt-1">{item.due_date ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Assignee
            </dt>
            <dd className="text-ink mt-1">{item.assignee_name ?? "Unassigned"}</dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Scope
            </dt>
            <dd className="text-ink mt-1">{item.scope === "BRAND" ? "Brand" : "Shop"}</dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Shop
            </dt>
            <dd className="text-ink mt-1">{item.shop_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
              Source
            </dt>
            <dd className="text-ink mt-1">
              {item.source === "AI" ? "AI extracted" : "Manual"}
            </dd>
          </div>
        </dl>
        <div className="pt-2 text-right">
          <button
            type="button"
            onClick={onEdit}
            className="text-[14px] text-muted underline hover:text-ink"
          >
            Edit Details
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="p-4 space-y-3" role="tabpanel">
      <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
        Title
        <input
          type="text"
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          className="mt-1 block w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          maxLength={200}
          minLength={5}
          disabled={saving}
        />
      </label>
      <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
        Priority
        <select
          value={draft.priority}
          onChange={(e) =>
            setDraft({ ...draft, priority: e.target.value as ActionItemPriority })
          }
          className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          disabled={saving}
        >
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </label>
      <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
        Due date
        <input
          type="date"
          value={draft.due_date}
          min={today}
          onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
          className="mt-1 block w-48 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          disabled={saving}
        />
      </label>
      <label className="block text-[12px] font-semibold uppercase tracking-[0.05em] text-muted">
        Assignee
        <select
          value={draft.assignee_id ?? ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              assignee_id: e.target.value ? Number(e.target.value) : null,
            })
          }
          className="mt-1 block w-64 px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-yellow"
          disabled={saving}
        >
          <option value="">Unassigned</option>
          {teamMembers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.full_name}
            </option>
          ))}
        </select>
      </label>
      {/* ACTN-07: Scope and Shop are NOT editable in any case. Rendered as
          read-only text per CONTEXT.md decision (applies to AI and manual). */}
      <div className="text-[12px] text-muted">
        Scope <span className="text-ink ml-2">{item.scope === "BRAND" ? "Brand" : "Shop"}</span>
        <span className="ml-3 text-muted">(not editable)</span>
      </div>
      <div className="text-[12px] text-muted">
        Shop <span className="text-ink ml-2">{item.shop_name ?? "—"}</span>
        <span className="ml-3 text-muted">(not editable)</span>
      </div>
      {error && (
        <p className="text-[12px] text-red mt-2" role="alert">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2 pt-4 mt-4 border-t border-line-soft">
        <button
          type="button"
          onClick={onCancelEdit}
          disabled={saving}
          className="px-4 py-2 text-[14px] bg-white border border-line rounded-md hover:bg-line-soft disabled:opacity-50"
        >
          Discard Changes
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

export function ActionItemModal({
  open,
  itemId,
  shops: _shops,
  teamMembers,
  onClose,
  onChanged,
}: Props) {
  const [item, setItem] = useState<ActionItemDetail | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("details");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<EditDraft>({
    title: "",
    priority: "MEDIUM",
    due_date: "",
    assignee_id: null,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || itemId == null) return;
    setItem(null);
    setActiveTab("details");
    setEditing(false);
    setError(null);
    void getActionItem(itemId).then(setItem).catch(() => setItem(null));
  }, [open, itemId]);

  if (!open) return null;

  const showSourceTab =
    item?.source === "AI" && item?.source_review !== null && item?.source_review !== undefined;

  const handleStatusChange = async (newStatus: ActionItemStatus) => {
    if (!item) return;
    try {
      const updated = await transitionStatus(item.id, newStatus);
      setItem(updated);
      emitToast({
        kind: "success",
        title: `Status updated to ${STATUS_LABEL[newStatus]}`,
      });
      onChanged();
    } catch {
      emitToast({
        kind: "error",
        title: "Could not update status. Please try again.",
      });
    }
  };

  const handleSave = async () => {
    if (!item) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateActionItemBackend(item.id, {
        title: draft.title,
        priority: draft.priority,
        due_date: draft.due_date || null,
        assignee: draft.assignee_id,
      });
      setItem(updated);
      setEditing(false);
      emitToast({ kind: "success", title: "Changes saved" });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleAddNote = async (body: string) => {
    if (!item) return;
    await addNote(item.id, body);
    const refreshed = await getActionItem(item.id);
    setItem(refreshed);
    emitToast({ kind: "success", title: "Note added" });
    onChanged();
  };

  const subtitle =
    item?.scope === "BRAND" ? "Brand" : `Shop · ${item?.shop_name ?? "—"}`;

  const tabs: { id: TabId; label: string }[] = [
    { id: "details", label: "Details" },
    { id: "notes", label: "Notes" },
    ...(showSourceTab ? ([{ id: "source", label: "Source Review" }] as const) : []),
  ];

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={item?.title ?? "Action item"}
      subtitle={item ? subtitle : undefined}
    >
      {!item ? (
        <div className="p-6 text-center text-[14px] text-muted">Loading…</div>
      ) : (
        <>
          <TabBar tabs={tabs} active={activeTab} onChange={setActiveTab} />
          {activeTab === "details" && (
            <DetailsTab
              item={item}
              editing={editing}
              draft={draft}
              setDraft={setDraft}
              onEdit={() => {
                setEditing(true);
                setDraft({
                  title: item.title,
                  priority: item.priority,
                  due_date: item.due_date ?? "",
                  assignee_id: item.assignee_id ?? null,
                });
              }}
              onCancelEdit={() => setEditing(false)}
              onSave={handleSave}
              onStatusChange={handleStatusChange}
              saving={saving}
              error={error}
              teamMembers={teamMembers}
            />
          )}
          {activeTab === "notes" && (
            <NotesTab notes={item.notes} onAddNote={handleAddNote} />
          )}
          {activeTab === "source" && showSourceTab && item.source_review && (
            <SourceReviewTab review={item.source_review} reviewId={item.source_review.id} />
          )}
        </>
      )}
    </Modal>
  );
}
