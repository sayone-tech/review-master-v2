// Phase 13 Plan 07 — Notes tab for ActionItemModal.
// Append-only timeline (oldest-first, ordering enforced server-side by
// ActionItemNote.Meta.ordering = ['created_at']) + always-visible compose area.
// ACTN-10: notes are append-only — no edit / delete UI.
import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { ActionItemNote } from "./types";

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  return d.toLocaleDateString();
}

function authorInitial(name: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

interface Props {
  notes: ActionItemNote[];
  onAddNote: (body: string) => Promise<void>;
}

export function NotesTab({ notes, onAddNote }: Props) {
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const charCount = draft.length;
  const trimmed = draft.trim();
  const disabled = submitting || trimmed.length === 0 || charCount > 2000;

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await onAddNote(trimmed);
      setDraft("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add note");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-4">
      <div className="space-y-0">
        {notes.length === 0 ? (
          <div className="text-[14px] text-muted py-4 text-center">No notes yet.</div>
        ) : (
          notes.map((note) => (
            <div
              key={note.id}
              className="flex gap-3 py-3 border-b border-line-soft last:border-b-0"
            >
              <span
                className="w-7 h-7 rounded-full bg-line flex items-center justify-center text-[12px] font-semibold text-muted shrink-0"
                aria-hidden="true"
              >
                {authorInitial(note.author_name)}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[12px] text-muted">
                  {note.author_name ?? "—"} · {formatRelativeDate(note.created_at)}
                </div>
                <div className="text-[14px] text-ink mt-1 whitespace-pre-wrap">
                  {note.body}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      <div className="mt-4 pt-4 border-t border-line-soft">
        <textarea
          aria-label="Add a note"
          aria-describedby="action-item-note-counter"
          className="w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md resize-none h-[80px] focus:outline-none focus:ring-2 focus:ring-yellow"
          maxLength={2000}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={submitting}
          placeholder="Write a note…"
        />
        <div
          id="action-item-note-counter"
          className="text-[12px] text-muted text-right mt-1"
          aria-live="polite"
        >
          {charCount} / 2000
        </div>
        {error && (
          <div className="text-[12px] text-red mt-1" role="alert">
            {error}
          </div>
        )}
        <div className="flex justify-end mt-2">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled}
            className="px-4 py-2 text-[14px] bg-yellow text-black font-semibold rounded-md hover:bg-yellow-hover disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-2"
          >
            {submitting && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
            {submitting ? "Adding…" : "Add note"}
          </button>
        </div>
      </div>
    </div>
  );
}
