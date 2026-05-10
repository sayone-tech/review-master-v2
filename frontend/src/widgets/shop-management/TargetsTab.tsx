import { useEffect, useState } from "react";
import type { TargetRow } from "./types";
import type { useTargets } from "./useTargets";

interface Props {
  shopId: number;
  isOrgAdmin: boolean;
  targets: ReturnType<typeof useTargets>;
  onAddTarget: () => void;
}

function progressColor(pct: number): string {
  if (pct >= 70) return "#16a34a"; // green
  if (pct >= 40) return "#d97706"; // amber
  return "#dc2626"; // red
}

function formatPeriodLabel(row: TargetRow): string {
  if (row.period_type === "MONTH") {
    const d = new Date(row.period_start + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }
  const start = new Date(row.period_start + "T00:00:00");
  const end = new Date(row.period_end + "T00:00:00");
  const fmt = (d: Date) =>
    d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `Week of ${fmt(start)}–${fmt(end)}`;
}

function isFuture(row: TargetRow): boolean {
  return new Date(row.period_start + "T00:00:00") > new Date();
}

function daysUntilStart(periodStart: string): number {
  const start = new Date(periodStart + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((start.getTime() - today.getTime()) / 86400000));
}

interface EditRowProps {
  row: TargetRow;
  onSave: (count: number) => void;
  onCancel: () => void;
}

function EditRow({ row, onSave, onCancel }: EditRowProps) {
  const [value, setValue] = useState(String(row.target_count));

  const trySubmit = () => {
    const count = parseInt(value, 10);
    if (!isNaN(count) && count >= 1) onSave(count);
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        min="1"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") trySubmit();
          if (e.key === "Escape") onCancel();
        }}
        className="w-24 border border-line rounded px-2 py-1 text-[13px] font-semibold"
        autoFocus
      />
      <span className="text-[11.5px] text-subtle">reviews</span>
      <button
        type="button"
        onClick={trySubmit}
        className="text-[11.5px] text-green-700 font-medium hover:underline"
      >
        Save
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-[11.5px] text-subtle hover:underline"
      >
        Cancel
      </button>
    </div>
  );
}

export function TargetsTab({ shopId: _shopId, isOrgAdmin, targets, onAddTarget }: Props) {
  const { rows, loading, error, load, editTarget, removeTarget } = targets;
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <p className="text-[13px] text-subtle py-4 text-center">Loading targets…</p>;
  }

  if (error) {
    return (
      <div className="py-4 text-center">
        <p className="text-[13px] text-red-600 mb-2">{error}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="text-[12px] text-ink underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="py-8 text-center">
        {isOrgAdmin ? (
          <>
            <p className="text-[13px] text-subtle mb-3">No targets set for this shop.</p>
            <button
              type="button"
              onClick={onAddTarget}
              className="px-4 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13px] font-semibold hover:bg-yellow-hover"
            >
              Set your first target →
            </button>
          </>
        ) : (
          <p className="text-[13px] text-subtle">No targets set.</p>
        )}
      </div>
    );
  }

  const handleSave = async (targetId: number, count: number) => {
    setActionError(null);
    const err = await editTarget(targetId, { target_count: count });
    if (err) {
      setActionError(err);
    } else {
      setEditingId(null);
    }
  };

  const handleDelete = async (targetId: number) => {
    setActionError(null);
    const err = await removeTarget(targetId);
    if (err) setActionError(err);
    setDeleteConfirmId(null);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <span className="text-[12px] text-subtle">Current &amp; upcoming targets</span>
        {isOrgAdmin && (
          <button
            type="button"
            onClick={onAddTarget}
            className="px-3 py-1.5 bg-yellow text-black border border-yellow-hover rounded-md text-[12px] font-semibold hover:bg-yellow-hover"
          >
            + Set Target
          </button>
        )}
      </div>

      {actionError && (
        <p className="text-[12px] text-red-600 mb-2">{actionError}</p>
      )}

      <div className="flex flex-col gap-2">
        {rows.map((row) => {
          const future = isFuture(row);
          const color = progressColor(row.pct);
          return (
            <div
              key={row.id}
              className={`rounded-lg p-3 ${future ? "border border-dashed border-line bg-surface-soft" : "border border-line"}`}
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="text-[12.5px] font-semibold text-ink">
                    {formatPeriodLabel(row)}
                  </div>
                  <div className="text-[10.5px] text-subtle mt-0.5">
                    {row.period_type === "MONTH" ? "Monthly" : "Weekly"} ·{" "}
                    {future
                      ? `starts in ${daysUntilStart(row.period_start)} days`
                      : `${row.days_remaining} days left`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {editingId === row.id ? (
                    <EditRow
                      row={row}
                      onSave={(count) => void handleSave(row.id, count)}
                      onCancel={() => setEditingId(null)}
                    />
                  ) : (
                    <>
                      {future ? (
                        <span className="text-[11px] font-medium text-subtle">
                          Target: {row.target_count}
                        </span>
                      ) : (
                        <span className="text-[11px] font-semibold text-ink">
                          {row.received_count} / {row.target_count}
                        </span>
                      )}
                      {isOrgAdmin && (
                        <>
                          <button
                            type="button"
                            onClick={() => setEditingId(row.id)}
                            className="text-subtle hover:text-ink text-[12px] p-0.5"
                            aria-label="Edit target"
                          >
                            ✎
                          </button>
                          {deleteConfirmId === row.id ? (
                            <span className="text-[11px] flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => void handleDelete(row.id)}
                                className="text-red-600 font-medium hover:underline"
                              >
                                Confirm
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeleteConfirmId(null)}
                                className="text-subtle hover:underline"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setDeleteConfirmId(row.id)}
                              className="text-red-400 hover:text-red-600 text-[12px] p-0.5"
                              aria-label="Delete target"
                            >
                              ✕
                            </button>
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>

              {!future && (
                <>
                  <div className="bg-gray-100 rounded h-1.5 overflow-hidden">
                    <div
                      className="h-full rounded"
                      style={{ width: `${Math.min(100, row.pct)}%`, backgroundColor: color }}
                    />
                  </div>
                  <div className="flex justify-between mt-1.5">
                    <span className="text-[10.5px] font-semibold" style={{ color }}>
                      {row.pct}% complete
                    </span>
                    <span className="text-[10.5px] text-subtle">
                      {Math.max(0, row.target_count - row.received_count)} more needed
                    </span>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
