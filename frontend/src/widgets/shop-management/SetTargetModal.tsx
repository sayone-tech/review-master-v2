import { useState } from "react";
import { Modal } from "../modal/Modal";
import type { TargetCreatePayload, TargetRow } from "./types";

interface Props {
  open: boolean;
  shopId: number;
  existingTargets: TargetRow[];
  onSave: (payload: TargetCreatePayload) => Promise<string | null>;
  onClose: () => void;
}

function getMonthOptions(existing: TargetRow[]): { label: string; value: string }[] {
  const existingKeys = new Set(
    existing
      .filter((t) => t.period_type === "MONTH")
      .map((t) => t.period_start),
  );
  const options: { label: string; value: string }[] = [];
  const today = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const iso = d.toISOString().split("T")[0];
    if (existingKeys.has(iso)) continue;
    const label =
      d.toLocaleDateString(undefined, { month: "long", year: "numeric" }) +
      (i === 0 ? " (current)" : "");
    options.push({ label, value: iso });
  }
  return options;
}

function getWeekOptions(existing: TargetRow[]): { label: string; value: string }[] {
  const existingKeys = new Set(
    existing
      .filter((t) => t.period_type === "WEEK")
      .map((t) => t.period_start),
  );
  const options: { label: string; value: string }[] = [];
  const today = new Date();
  const dayOfWeek = today.getDay();
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const currentMonday = new Date(today);
  currentMonday.setDate(today.getDate() + mondayOffset);

  for (let i = 0; i < 52; i++) {
    const monday = new Date(currentMonday);
    monday.setDate(currentMonday.getDate() + i * 7);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    const iso = monday.toISOString().split("T")[0];
    if (existingKeys.has(iso)) continue;
    const fmt = (d: Date) =>
      d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const label = `${fmt(monday)} – ${fmt(sunday)}` + (i === 0 ? " (current)" : "");
    options.push({ label, value: iso });
  }
  return options;
}

export function SetTargetModal({ open, shopId: _shopId, existingTargets, onSave, onClose }: Props) {
  const [periodType, setPeriodType] = useState<"MONTH" | "WEEK">("MONTH");
  const [periodStart, setPeriodStart] = useState(() => {
    const opts = getMonthOptions(existingTargets);
    return opts[0]?.value ?? "";
  });
  const [targetCount, setTargetCount] = useState("100");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const monthOptions = getMonthOptions(existingTargets);
  const weekOptions = getWeekOptions(existingTargets);
  const options = periodType === "MONTH" ? monthOptions : weekOptions;

  const handlePeriodTypeChange = (pt: "MONTH" | "WEEK") => {
    setPeriodType(pt);
    const opts =
      pt === "MONTH" ? getMonthOptions(existingTargets) : getWeekOptions(existingTargets);
    setPeriodStart(opts[0]?.value ?? "");
    setError(null);
  };

  const handleSave = async () => {
    if (!periodStart) {
      setError("Please select a period.");
      return;
    }
    const count = parseInt(targetCount, 10);
    if (isNaN(count) || count < 1) {
      setError("Target must be at least 1.");
      return;
    }
    setSaving(true);
    setError(null);
    const err = await onSave({
      period_type: periodType,
      period_start: periodStart,
      target_count: count,
    });
    setSaving(false);
    if (err) {
      setError(err);
    } else {
      onClose();
      setPeriodType("MONTH");
      setPeriodStart("");
      setTargetCount("100");
    }
  };

  return (
    <Modal
      open={open}
      title="Set Review Target"
      size="sm"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 bg-white text-ink border border-line rounded-md text-[13.5px] font-medium hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || options.length === 0}
            className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-semibold hover:bg-yellow-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Target"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Period Type
          </div>
          <div className="flex gap-2">
            {(["MONTH", "WEEK"] as const).map((pt) => (
              <button
                key={pt}
                type="button"
                onClick={() => handlePeriodTypeChange(pt)}
                className={`flex-1 py-2 rounded-md text-[12.5px] font-semibold border transition-colors ${
                  periodType === pt
                    ? "border-yellow bg-yellow/10 text-ink"
                    : "border-line bg-white text-subtle hover:bg-line-soft"
                }`}
              >
                {pt === "MONTH" ? "Monthly" : "Weekly"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Period
          </div>
          {options.length === 0 ? (
            <p className="text-[12px] text-subtle italic">
              All {periodType === "MONTH" ? "monthly" : "weekly"} periods have targets set.
            </p>
          ) : (
            <select
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-full border border-line rounded-md px-3 py-2 text-[13px] text-ink bg-white"
            >
              {options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <div className="text-[10.5px] font-semibold uppercase tracking-wide text-subtle mb-1.5">
            Review Target
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="1"
              value={targetCount}
              onChange={(e) => setTargetCount(e.target.value)}
              className="flex-1 border border-line rounded-md px-3 py-2 text-[13.5px] font-semibold"
            />
            <span className="text-[12px] text-subtle whitespace-nowrap">reviews</span>
          </div>
        </div>

        {error && <p className="text-[12px] text-red-600">{error}</p>}
      </div>
    </Modal>
  );
}
