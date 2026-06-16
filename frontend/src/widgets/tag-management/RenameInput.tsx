// Phase 25-03 — Inline rename input for a canonical tag row.
// Keyboard: Enter = submit, Escape = cancel.

import { useEffect, useRef, useState } from "react";
import { ApiError, renameTag } from "./api";
import type { OrgCanonicalTagRow } from "./types";

interface Props {
  row: OrgCanonicalTagRow;
  onSaved: (updated: OrgCanonicalTagRow) => void;
  onCancel: () => void;
}

function mapServerError(err: unknown): string {
  if (err instanceof ApiError) {
    const data = err.data as Record<string, unknown> | null;
    if (data) {
      const detail =
        (typeof data.label === "string" && data.label) ||
        (Array.isArray(data.label) && typeof data.label[0] === "string" && data.label[0]) ||
        (typeof data.detail === "string" && data.detail);
      if (typeof detail === "string") {
        const lower = detail.toLowerCase();
        if (lower.includes("already exists") || lower.includes("duplicate")) {
          return "A tag with that name already exists. Use Merge to combine tags.";
        }
      }
    }
  }
  return "Could not rename. Please try again.";
}

export function RenameInput({ row, onSaved, onCancel }: Props) {
  const [value, setValue] = useState(row.label);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Label cannot be empty.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await renameTag(row.id, trimmed);
      onSaved(updated);
    } catch (err) {
      setError(mapServerError(err));
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      void handleSave();
    } else if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <div className="flex flex-col gap-1 w-full">
      <div className="flex items-center gap-1">
        <input
          ref={inputRef}
          type="text"
          aria-label="Rename tag"
          className="w-full h-8 px-2 py-1 text-[14px] text-ink bg-white border border-line rounded-sm focus:outline-none focus:border-yellow focus:ring-1 focus:ring-yellow/40 disabled:opacity-60"
          maxLength={100}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          readOnly={saving}
          disabled={saving}
        />
        <button
          type="button"
          aria-label="Save label"
          disabled={saving}
          onClick={() => void handleSave()}
          className="ml-2 px-3 py-1 bg-yellow text-black text-[12px] font-semibold rounded-sm hover:bg-yellow-hover disabled:opacity-50 whitespace-nowrap"
        >
          {saving ? "Saving…" : "Save Label"}
        </button>
        <button
          type="button"
          aria-label="Cancel rename"
          disabled={saving}
          onClick={onCancel}
          className="ml-1 px-3 py-1 bg-white text-ink border border-line text-[12px] rounded-sm hover:bg-line-soft disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
      {error && (
        <p role="alert" className="text-[12px] text-red mt-1">
          {error}
        </p>
      )}
    </div>
  );
}
