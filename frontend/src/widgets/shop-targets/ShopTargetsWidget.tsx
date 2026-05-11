import { AlertCircle, Check, ChevronDown, ChevronUp, Target, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteTarget, fetchTargetHistory, listTargets, setTarget } from "./api";
import type { TargetHistoryRow, TargetRow } from "./types";

// ─── Design-system class constants ───────────────────────────────────────────
const BTN_BASE =
  "inline-flex items-center justify-center gap-1.5 font-medium border transition-[background,border-color,color] duration-[120ms] focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed";
const BTN_MD = "px-3.5 py-2 text-[13.5px] rounded-md";
const BTN_SM = "px-2.5 py-[5px] text-[12.5px] rounded-sm";
const BTN_PRIMARY = "bg-yellow text-black border-yellow-hover hover:bg-yellow-hover";
const BTN_SECONDARY = "bg-white text-ink border-line hover:bg-line-soft hover:border-[#D4D4D8]";
const BTN_DANGER = "bg-red text-white border-transparent hover:bg-[#B91C1C]";

const INPUT_BASE =
  "w-full px-3 py-[9px] text-[13.5px] bg-white border rounded-md text-text placeholder:text-faint focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink";
const LABEL_BASE = "block text-[13px] font-medium text-ink mb-1.5";

function barColor(pct: number): string {
  if (pct >= 70) return "bg-green";
  if (pct >= 40) return "bg-amber";
  return "bg-red";
}

interface Props {
  shopId: number;
  shopName: string;
  isOrgAdmin: boolean;
}

function HistorySection({
  shopId,
  periodType,
}: {
  shopId: number;
  periodType: "WEEK" | "MONTH";
}) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<TargetHistoryRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (rows !== null) return;
    setLoading(true);
    setError(null);
    try {
      setRows(await fetchTargetHistory(shopId, periodType));
    } catch {
      setError("Could not load history.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-t border-line-soft pt-3">
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex items-center gap-1 text-[12.5px] text-subtle hover:text-ink transition-colors focus:outline-none"
      >
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        Past periods
      </button>

      {open && (
        <div className="mt-3">
          {loading && <p className="text-[12px] text-muted">Loading…</p>}
          {error && (
            <p className="text-[12px] text-red flex items-center gap-1">
              <AlertCircle size={12} />
              {error}
            </p>
          )}
          {rows && rows.length === 0 && (
            <p className="text-[12px] text-muted">No previous periods found.</p>
          )}
          {rows && rows.length > 0 && (
            <table className="w-full">
              <thead>
                <tr className="border-b border-line-soft">
                  <th className="pb-2 text-left text-[11px] font-semibold uppercase tracking-wide text-subtle">
                    Period
                  </th>
                  <th className="pb-2 text-right text-[11px] font-semibold uppercase tracking-wide text-subtle">
                    Reviews
                  </th>
                  <th className="pb-2 w-14 text-right text-[11px] font-semibold uppercase tracking-wide text-subtle">
                    %
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.period_start} className="border-b border-line-soft last:border-0">
                    <td className="py-2 text-[13px] text-muted">{r.period_label}</td>
                    <td className="py-2 text-right text-[13px] tabular-nums text-ink">
                      {r.received_count}
                      <span className="text-subtle"> / {r.target_count}</span>
                    </td>
                    <td className="py-2 text-right text-[13px] tabular-nums font-medium">
                      <span
                        className={
                          r.pct >= 70 ? "text-green" : r.pct >= 40 ? "text-amber" : "text-red"
                        }
                      >
                        {r.pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
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
    setError(null);
  }

  function cancelEdit() {
    setEditing(false);
    setError(null);
  }

  async function handleSave() {
    const count = parseInt(inputValue, 10);
    if (Number.isNaN(count) || count < 1) {
      setError("Enter a whole number ≥ 1.");
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

  // ── Empty state (no target set) ──────────────────────────────────────────
  if (!row) {
    return (
      <div className="bg-white border border-line rounded-card p-6 flex flex-col gap-5">
        <h3 className="text-[14px] font-semibold text-ink">{label} Target</h3>

        <div className="flex flex-col items-center gap-2 py-4 text-center">
          <div className="w-10 h-10 rounded-full bg-line-soft flex items-center justify-center text-muted">
            <Target size={20} strokeWidth={1.5} />
          </div>
          <p className="text-[13.5px] font-medium text-ink">No target set</p>
          <p className="text-[12.5px] text-subtle">
            Set a goal to track how many reviews this shop receives.
          </p>
        </div>

        {error && (
          <p className="text-[12px] text-red flex items-center gap-1" role="alert">
            <AlertCircle size={12} />
            {error}
          </p>
        )}

        {isOrgAdmin &&
          (editing ? (
            <div className="flex flex-col gap-2">
              <div>
                <label htmlFor={`target-input-${periodType}`} className={LABEL_BASE}>
                  Target (reviews)
                </label>
                <input
                  id={`target-input-${periodType}`}
                  type="number"
                  min={1}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  className={`${INPUT_BASE} ${error ? "border-red" : "border-line"} w-28`}
                  autoFocus
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className={`${BTN_BASE} ${BTN_MD} ${BTN_PRIMARY}`}
                >
                  <Check size={14} />
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className={`${BTN_BASE} ${BTN_MD} ${BTN_SECONDARY}`}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={startEdit}
              className={`${BTN_BASE} ${BTN_MD} ${BTN_PRIMARY} self-center`}
            >
              + Set Target
            </button>
          ))}
      </div>
    );
  }

  // ── Card with target set ─────────────────────────────────────────────────
  return (
    <div className="bg-white border border-line rounded-card p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-semibold text-ink">{label} Target</h3>
        <span className="text-[12px] text-subtle bg-line-soft rounded px-2 py-0.5">
          {row.period_label}
        </span>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-end justify-between">
          <span className="text-[28px] font-bold text-ink leading-none tabular-nums">
            {row.received_count}
            <span className="text-[15px] font-normal text-muted"> / {row.target_count}</span>
          </span>
          <span
            className={`text-[12.5px] font-semibold px-2 py-0.5 rounded-full ${
              row.pct >= 70
                ? "text-green bg-green/10"
                : row.pct >= 40
                  ? "text-amber bg-amber/10"
                  : "text-red bg-red/10"
            }`}
          >
            {row.pct}%
          </span>
        </div>

        <div className="h-1.5 bg-line-soft rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${barColor(row.pct)}`}
            style={{ width: `${Math.min(row.pct, 100)}%` }}
          />
        </div>

        <p className="text-[12px] text-subtle">
          {row.days_remaining === 0
            ? "Last day of this period"
            : `${row.days_remaining} day${row.days_remaining !== 1 ? "s" : ""} remaining`}
        </p>
      </div>

      {error && (
        <p className="text-[12px] text-red flex items-center gap-1" role="alert">
          <AlertCircle size={12} />
          {error}
        </p>
      )}

      <HistorySection shopId={shopId} periodType={periodType} />

      {isOrgAdmin && (
        <div className="border-t border-line-soft pt-4">
          {editing ? (
            <div className="flex flex-col gap-2">
              <div>
                <label htmlFor={`target-input-${periodType}`} className={LABEL_BASE}>
                  New target (reviews)
                </label>
                <input
                  id={`target-input-${periodType}`}
                  type="number"
                  min={1}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  className={`${INPUT_BASE} ${error ? "border-red" : "border-line"} w-28`}
                  autoFocus
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className={`${BTN_BASE} ${BTN_MD} ${BTN_PRIMARY}`}
                >
                  <Check size={14} />
                  {saving ? "Saving…" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className={`${BTN_BASE} ${BTN_MD} ${BTN_SECONDARY}`}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : confirmDelete ? (
            <div className="flex items-center gap-3">
              <p className="text-[13px] text-ink flex-1">Remove this target?</p>
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={deleting}
                className={`${BTN_BASE} ${BTN_SM} ${BTN_DANGER}`}
              >
                <Trash2 size={12} />
                {deleting ? "Deleting…" : "Delete"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className={`${BTN_BASE} ${BTN_SM} ${BTN_SECONDARY}`}
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={startEdit}
                className={`${BTN_BASE} ${BTN_SM} ${BTN_SECONDARY}`}
              >
                Edit target
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className={`${BTN_BASE} ${BTN_SM} ${BTN_DANGER}`}
              >
                <Trash2 size={12} />
                Remove
              </button>
            </div>
          )}
        </div>
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

      <h1 className="text-[22px] font-semibold text-ink tracking-[-0.02em] mb-1">
        Review Targets
      </h1>
      <p className="text-[14px] text-muted mb-6">
        Track how many reviews this shop receives each week and month.
      </p>

      {loading ? (
        <p className="text-[13px] text-muted">Loading…</p>
      ) : loadError ? (
        <p className="text-[12px] text-red flex items-center gap-1" role="alert">
          <AlertCircle size={12} />
          {loadError}
        </p>
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
