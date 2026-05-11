import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteTarget, listTargets, setTarget } from "./api";
import type { TargetRow } from "./types";

interface Props {
  shopId: number;
  shopName: string;
  isOrgAdmin: boolean;
}

function barColor(pct: number): string {
  if (pct >= 70) return "bg-green";
  if (pct >= 40) return "bg-amber";
  return "bg-red";
}

interface CardProps {
  periodType: "WEEK" | "MONTH";
  row: TargetRow | undefined;
  isOrgAdmin: boolean;
  shopId: number;
  onChanged: () => void;
}

function TargetCard({ periodType, row, isOrgAdmin, shopId, onChanged }: CardProps) {
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = periodType === "WEEK" ? "Weekly" : "Monthly";

  function startEdit() {
    setInputValue(row ? String(row.target_count) : "");
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setError(null);
  }

  async function handleSave() {
    const count = parseInt(inputValue, 10);
    if (Number.isNaN(count) || count < 1) {
      setError("Enter a whole number ≥ 1");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await setTarget(shopId, { period_type: periodType, target_count: count });
      setEditing(false);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? "Failed to save. Try again." : "Unexpected error.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!row) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteTarget(shopId, row.id);
      setConfirmDelete(false);
      onChanged();
    } catch {
      setError("Failed to delete. Try again.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="bg-white border border-line rounded-card p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-[14px] font-semibold text-ink">{label}</span>
        {row && <span className="text-[12px] text-muted">{row.period_label}</span>}
      </div>

      {row ? (
        <>
          <div>
            <div className="h-2 bg-line-soft rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${barColor(row.pct)}`}
                style={{ width: `${Math.min(row.pct, 100)}%` }}
              />
            </div>
            <div className="flex justify-between mt-1.5">
              <span className="text-[13px] text-ink">
                {row.received_count} / {row.target_count} reviews
              </span>
              <span className="text-[12px] text-muted">{row.pct}%</span>
            </div>
          </div>

          <span className="text-[12px] text-subtle">
            {row.days_remaining === 0
              ? "Last day of period"
              : `${row.days_remaining} day${row.days_remaining !== 1 ? "s" : ""} remaining`}
          </span>

          {error && <p className="text-[12px] text-red">{error}</p>}

          {isOrgAdmin && (
            <>
              {editing ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    className="w-20 border border-line rounded px-2 py-1 text-[13px] focus:outline-none focus:ring-1 focus:ring-yellow"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={saving}
                    className="px-3 py-1 bg-yellow text-black text-[13px] font-semibold rounded hover:bg-yellow-hover disabled:opacity-50"
                  >
                    {saving ? "Saving…" : "Save"}
                  </button>
                  <button
                    type="button"
                    onClick={cancelEdit}
                    className="px-3 py-1 text-[13px] text-muted border border-line rounded hover:bg-bg"
                  >
                    Cancel
                  </button>
                </div>
              ) : confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-[13px] text-ink">Remove this target?</span>
                  <button
                    type="button"
                    onClick={() => void handleDelete()}
                    disabled={deleting}
                    className="px-3 py-1 text-[13px] text-red border border-line rounded hover:bg-red-tint disabled:opacity-50"
                  >
                    {deleting ? "Deleting…" : "Delete"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="px-3 py-1 text-[13px] text-muted border border-line rounded hover:bg-bg"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={startEdit}
                    className="px-3 py-1 text-[13px] text-muted border border-line rounded hover:bg-bg"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="px-3 py-1 text-[13px] text-red border border-line rounded hover:bg-red-tint"
                  >
                    Delete
                  </button>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <p className="text-[13px] text-muted">No target set.</p>
          {error && <p className="text-[12px] text-red">{error}</p>}
          {isOrgAdmin &&
            (editing ? (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  className="w-20 border border-line rounded px-2 py-1 text-[13px] focus:outline-none focus:ring-1 focus:ring-yellow"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className="px-3 py-1 bg-yellow text-black text-[13px] font-semibold rounded hover:bg-yellow-hover disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="px-3 py-1 text-[13px] text-muted border border-line rounded hover:bg-bg"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={startEdit}
                className="self-start px-3 py-1.5 text-[13px] font-medium text-muted border border-line rounded hover:bg-bg"
              >
                + Set Target
              </button>
            ))}
        </>
      )}
    </div>
  );
}

export function ShopTargetsWidget({ shopId, shopName, isOrgAdmin }: Props) {
  const [targets, setTargets] = useState<TargetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setTargets(await listTargets(shopId));
    } catch {
      setLoadError("Could not load targets. Try refreshing.");
    } finally {
      setLoading(false);
    }
  }, [shopId]);

  useEffect(() => {
    void load();
  }, [load]);

  const weekly = targets.find((t) => t.period_type === "WEEK");
  const monthly = targets.find((t) => t.period_type === "MONTH");

  return (
    <div>
      <nav className="flex items-center gap-1 text-[13px] text-muted mb-4">
        <a href="/admin/org/shops/" className="hover:text-ink">
          Shops
        </a>
        <span>/</span>
        <span className="text-ink">{shopName}</span>
        <span>/</span>
        <span className="text-ink font-medium">Review Targets</span>
      </nav>

      <h1 className="text-[18px] font-semibold text-ink mb-6">Review Targets</h1>

      {loading ? (
        <p className="text-[13px] text-muted">Loading…</p>
      ) : loadError ? (
        <p className="text-[13px] text-red">{loadError}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TargetCard
            periodType="WEEK"
            row={weekly}
            isOrgAdmin={isOrgAdmin}
            shopId={shopId}
            onChanged={() => void load()}
          />
          <TargetCard
            periodType="MONTH"
            row={monthly}
            isOrgAdmin={isOrgAdmin}
            shopId={shopId}
            onChanged={() => void load()}
          />
        </div>
      )}
    </div>
  );
}
