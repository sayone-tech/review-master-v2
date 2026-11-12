import { useId, useState } from "react";
import { ConfirmModal } from "../modal/ConfirmModal";
import { deleteScheduledPrice } from "./api";
import { Money } from "../ai-cost/Money";
import { Badge } from "../ai-cost/PageHeader";
import { formatDate, formatDateTime, formatPrice, sourceLabel } from "./format";
import type { PriceRow } from "./types";

const LOCKED_TIP = "This price is or has been in effect, so it can't be deleted.";

function StatusBadge({ status }: { status: PriceRow["status"] }) {
  if (status === "current")
    return (
      <Badge tone="green" dot>
        Current
      </Badge>
    );
  if (status === "scheduled") return <Badge tone="yellow">Scheduled</Badge>;
  return null;
}

const DOT: Record<PriceRow["status"], string> = {
  current: "bg-green",
  scheduled: "bg-yellow",
  historical: "bg-faint",
};

function period(r: PriceRow): string {
  if (r.status === "scheduled") return `From ${formatDateTime(r.effective_from)}`;
  return `${formatDate(r.effective_from)} to ${r.effective_to ? formatDate(r.effective_to) : "now"}`;
}

function DeleteButton({ row, onDelete }: { row: PriceRow; onDelete: (r: PriceRow) => void }) {
  const reasonId = useId();
  const locked = !row.can_delete;
  return (
    <>
      <button
        type="button"
        className={`rounded-sm text-[12.5px] font-medium text-red underline-offset-2 hover:underline${locked ? " opacity-40 no-underline cursor-not-allowed" : ""}`}
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

function setBy(row: PriceRow): string | null {
  return row.created_by ? (row.created_by.name ?? row.created_by.email ?? null) : null;
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
      <ol className="ml-1 border-l border-line" aria-label="Price history">
        {rows.map((r) => {
          const who = setBy(r);
          return (
            <li key={r.id} className="relative pb-4 pl-5 last:pb-0">
              <span
                aria-hidden="true"
                className={`absolute -left-[4.5px] top-[6px] h-2 w-2 rounded-full ring-2 ring-[#FBFBFB] ${DOT[r.status]}`}
              />
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                <span className="text-[13px] font-medium text-ink tabular-nums">{period(r)}</span>
                <StatusBadge status={r.status} />
                <Badge>{sourceLabel(r.source)}</Badge>
                {who && <span className="text-[12.5px] text-muted">Set by {who}</span>}
                {(r.status === "scheduled" || r.can_delete) && (
                  <span className="ml-auto">
                    <DeleteButton row={r} onDelete={setPending} />
                  </span>
                )}
              </div>
              <p className="mt-1 text-[12.5px] text-muted tabular-nums">
                Input <Money value={formatPrice(r.input_token_price_per_1m)} className="text-ink" />
                <span className="mx-2" />
                Output <Money value={formatPrice(r.output_token_price_per_1m)} className="text-ink" />
                <span className="mx-2" />
                Cached <Money value={formatPrice(r.cached_token_price_per_1m)} className="text-ink" />
              </p>
            </li>
          );
        })}
      </ol>
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
