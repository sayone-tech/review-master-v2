import { useId, useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { deleteScheduledPrice } from "./api";
import { formatDate, formatDateTime, formatPrice, sourceLabel } from "./format";
import type { PriceRow } from "./types";

const LOCKED_TIP = "This pricing is in effect or has been in effect — can't delete.";

function Pill({ status }: { status: PriceRow["status"] }) {
  if (status === "current")
    return <span className="rounded-full bg-green-tint text-green px-2 py-0.5 text-[11px] font-medium">Current</span>;
  if (status === "scheduled")
    return <span className="rounded-full bg-amber-tint text-amber px-2 py-0.5 text-[11px] font-medium">Scheduled</span>;
  return null;
}

function DeleteButton({ row, onDelete }: { row: PriceRow; onDelete: (r: PriceRow) => void }) {
  const reasonId = useId();
  const locked = !row.can_delete;
  return (
    <>
      <button
        type="button"
        className={`text-[12.5px] font-medium text-red hover:underline${locked ? " opacity-40 no-underline cursor-not-allowed" : ""}`}
        aria-disabled={locked || undefined}
        aria-describedby={locked ? reasonId : undefined}
        title={locked ? LOCKED_TIP : undefined}
        onClick={() => {
          if (!locked) onDelete(row);
        }}
      >
        Delete
      </button>
      {locked && (
        <span id={reasonId} className="sr-only">
          {LOCKED_TIP}
        </span>
      )}
    </>
  );
}

function setBy(row: PriceRow): string {
  return row.created_by ? (row.created_by.name ?? row.created_by.email ?? "—") : "—";
}

interface Props {
  rows: PriceRow[];
  /** Called after a scheduled price was deleted so the parent can refetch. */
  onDeleted: () => void;
}

export function HistoryRows({ rows, onDeleted }: Props) {
  const [pending, setPending] = useState<PriceRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!pending) return;
    const id = pending.id;
    setPending(null);
    setError(null);
    try {
      await deleteScheduledPrice(id);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete price");
    }
  };

  return (
    <>
      {error && (
        <div role="alert" className="text-[13px] text-red mb-2">
          {error}
        </div>
      )}
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="text-[12px] text-muted border-b border-line">
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Effective from</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Effective to</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Input</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Output</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Cached</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Status</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Source</th>
            <th scope="col" className="py-1.5 pr-3 text-left font-medium">Set by</th>
            <th scope="col" className="py-1.5 text-left font-medium"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0">
              <td className="py-2 pr-3">
                {r.status === "scheduled" ? formatDateTime(r.effective_from) : formatDate(r.effective_from)}
              </td>
              <td className="py-2 pr-3">{r.effective_to ? formatDate(r.effective_to) : "—"}</td>
              <td className="py-2 pr-3">{formatPrice(r.input_token_price_per_1m)}</td>
              <td className="py-2 pr-3">{formatPrice(r.output_token_price_per_1m)}</td>
              <td className="py-2 pr-3">{formatPrice(r.cached_token_price_per_1m)}</td>
              <td className="py-2 pr-3"><Pill status={r.status} /></td>
              <td className="py-2 pr-3">{sourceLabel(r.source)}</td>
              <td className="py-2 pr-3">{setBy(r)}</td>
              <td className="py-2">
                <DeleteButton row={r} onDelete={setPending} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ConfirmModal
        open={pending !== null}
        onClose={() => setPending(null)}
        onConfirm={() => void confirm()}
        variant="red"
        title="Delete scheduled price?"
        message={
          pending
            ? `The scheduled price for ${pending.model} starting ${formatDateTime(pending.effective_from)} will be removed. The current price stays in effect.`
            : ""
        }
        confirmLabel="Delete"
      />
    </>
  );
}
