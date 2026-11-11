import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Modal } from "../modal";
import { emitToast } from "../../lib/toast";
import { allocateBonus, type CreditPeriod, type CreditShopRow } from "./creditsApi";
import { formatCount, formatMonthYear } from "./creditHint";
import { useCreditShops } from "./useCreditShops";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
}

const AMOUNT_MIN = 1;
const AMOUNT_MAX = 10000;

const secondaryBtn =
  "inline-flex items-center justify-center bg-white text-ink border border-line rounded-md font-normal hover:bg-line-soft";
const inputCls =
  "w-full px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.05] focus:border-ink";

/** Whole number 1..10,000, else null (empty, decimals and out-of-range are invalid). */
function parseAmount(raw: string): number | null {
  const t = raw.trim();
  if (!/^\d+$/.test(t)) return null;
  const n = Number(t);
  return n >= AMOUNT_MIN && n <= AMOUNT_MAX ? n : null;
}

function plural(n: number): string {
  return `${formatCount(n)} ${n === 1 ? "credit" : "credits"}`;
}

function currentUtcPeriod(): CreditPeriod {
  const now = new Date();
  return { year: now.getUTCFullYear(), month: now.getUTCMonth() + 1 };
}

export function ManageCreditsModal({ org, onClose }: Props) {
  const { data, loading, search, setSearch, reload } = useCreditShops(org?.id ?? null);

  const [view, setView] = useState<"list" | "bonus">("list");
  const [shop, setShop] = useState<CreditShopRow | null>(null);
  const [bonusPeriod, setBonusPeriod] = useState<CreditPeriod>(currentUtcPeriod());
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const amountRef = useRef<HTMLInputElement | null>(null);

  // Reset to a clean list view when the modal opens for a (different) organisation.
  useEffect(() => {
    setView("list");
    setShop(null);
    setAmount("");
    setReason("");
    setSubmitting(false);
  }, [org?.id]);

  useEffect(() => {
    if (view === "bonus") amountRef.current?.focus();
  }, [view]);

  if (!org) return null;
  const currentOrg = org;

  const period = data?.period ?? currentUtcPeriod();
  const perShop = data?.allocation_per_shop ?? currentOrg.current_month_credit_allocation;
  const listSubtitle = `${currentOrg.name} — ${formatMonthYear(period.year, period.month)} · ${plural(perShop)} per shop`;

  const amountValue = parseAmount(amount);

  function openBonus(row: CreditShopRow) {
    setShop(row);
    setBonusPeriod(period);
    setAmount("");
    setReason("");
    setView("bonus");
  }

  function backToList() {
    if (submitting) return;
    setAmount("");
    setReason("");
    setView("list");
  }

  async function handleAllocate() {
    if (submitting || amountValue === null || !shop) return;
    setSubmitting(true);
    try {
      const trimmedReason = reason.trim();
      await allocateBonus(shop.id, {
        amount: amountValue,
        period_year: bonusPeriod.year,
        period_month: bonusPeriod.month,
        ...(trimmedReason ? { reason: trimmedReason } : {}),
      });
      emitToast({ kind: "success", title: `Added ${plural(amountValue)} to ${shop.name}.` });
      setAmount("");
      setReason("");
      setView("list");
      await reload();
    } catch {
      emitToast({
        kind: "error",
        title: "Something went wrong.",
        msg: "Please try again. If the problem persists, contact support.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (view === "bonus" && shop) {
    const invalid = amountValue === null;
    return (
      <Modal
        open
        onClose={onClose}
        size="lg"
        title="Add Bonus Credits"
        subtitle={`${shop.name} — ${formatMonthYear(bonusPeriod.year, bonusPeriod.month)}`}
        footer={
          <>
            <button
              type="button"
              onClick={backToList}
              disabled={submitting}
              className={`${secondaryBtn} h-10 px-4 text-[14px]`}
              data-testid="credits-back"
            >
              Back to list
            </button>
            <button
              type="button"
              onClick={handleAllocate}
              disabled={invalid || submitting}
              className={`inline-flex items-center justify-center gap-2 bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover rounded-md h-10 px-4 text-[14px] font-semibold ${
                invalid || submitting ? "opacity-50 cursor-not-allowed pointer-events-none" : ""
              }`}
              data-testid="credits-allocate"
            >
              {submitting && (
                <span
                  className="w-4 h-4 rounded-full border-2 border-black/30 border-t-black animate-spin"
                  aria-hidden="true"
                />
              )}
              Allocate
            </button>
          </>
        }
      >
        <dl
          className="bg-line-soft rounded-md p-4 grid grid-cols-2 sm:grid-cols-4 gap-4"
          data-testid="credits-balance-block"
        >
          {(
            [
              ["Monthly allocation", shop.allocated],
              ["Bonus so far", shop.bonus],
              ["Used", shop.consumed],
              ["Remaining", shop.remaining],
            ] as const
          ).map(([label, value]) => (
            <div key={label}>
              <dt className="text-[12px] text-subtle uppercase tracking-[0.05em]">{label}</dt>
              <dd className="text-[14px] font-semibold text-ink">{formatCount(value)}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-4">
          <label
            htmlFor="credits-amount"
            className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1"
          >
            Additional credits to allocate
          </label>
          <input
            id="credits-amount"
            ref={amountRef}
            type="number"
            min={AMOUNT_MIN}
            max={AMOUNT_MAX}
            step={1}
            inputMode="numeric"
            value={amount}
            disabled={submitting}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="e.g. 50"
            className={inputCls}
            data-testid="credits-amount"
          />
          <p className="mt-1 text-[12px] text-muted">Whole number from 1 to 10,000.</p>
        </div>

        <div
          className="mt-4 border border-line rounded-md px-4 py-2 text-[13px] min-h-[56px]"
          data-testid="credits-preview"
          aria-live="polite"
        >
          <div className="text-[12px] text-subtle">After this allocation</div>
          {amountValue === null ? (
            <div className="text-muted">Enter an amount to preview the new balance.</div>
          ) : (
            <div>
              <span className="text-muted">Remaining {formatCount(shop.remaining)}</span>
              {" → "}
              <span className="text-ink font-semibold">
                {formatCount(shop.remaining + amountValue)}
              </span>
              {" · "}
              <span className="text-muted">Bonus {formatCount(shop.bonus)}</span>
              {" → "}
              <span className="text-ink font-semibold">
                {formatCount(shop.bonus + amountValue)}
              </span>
            </div>
          )}
        </div>

        <div className="mt-4">
          <label
            htmlFor="credits-reason"
            className="block text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-1"
          >
            Reason{" "}
            <span className="text-faint font-normal normal-case tracking-normal">(optional)</span>
          </label>
          <textarea
            id="credits-reason"
            rows={3}
            maxLength={255}
            value={reason}
            disabled={submitting}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Goodwill credit after outage"
            className={inputCls}
            data-testid="credits-reason"
          />
        </div>
      </Modal>
    );
  }

  const rows = data?.results ?? [];
  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Manage Credits"
      subtitle={listSubtitle}
      footer={
        <button
          type="button"
          onClick={onClose}
          className={`${secondaryBtn} h-10 px-4 text-[14px]`}
          data-testid="credits-close"
        >
          Close
        </button>
      }
    >
      <div className="relative">
        <Search
          size={16}
          aria-hidden="true"
          className="absolute left-2 top-1/2 -translate-y-1/2 text-subtle pointer-events-none"
        />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search shops by name"
          aria-label="Search shops by name"
          autoFocus
          className="w-full pl-8 pr-4 py-2 text-[13px] bg-bg border border-line rounded-md focus:outline-none focus:border-ink focus:ring focus:ring-black/[0.05]"
          data-testid="credits-search"
        />
      </div>

      <div
        className="bg-white border border-line rounded-card overflow-hidden mt-4"
        aria-busy={loading}
      >
        <ul>
          {rows.map((row) => (
            <li
              key={row.id}
              data-testid={`credits-row-${row.id}`}
              className="px-4 py-4 border-b border-line-soft last:border-b-0 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
            >
              <div className="min-w-0">
                <div className="text-[14px] font-semibold text-ink break-words">{row.name}</div>
                <div className="text-[12px] text-subtle">
                  {`Monthly ${formatCount(row.allocated)} · Bonus ${formatCount(row.bonus)} · Used ${formatCount(row.consumed)}`}
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div>
                  <span className="text-[12px] text-muted">Remaining </span>
                  <span className="text-[14px] font-semibold text-ink">
                    {formatCount(row.remaining)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => openBonus(row)}
                  aria-label={`Add bonus credits for ${row.name}`}
                  className={`${secondaryBtn} h-8 px-4 text-[13px]`}
                  data-testid={`credits-add-bonus-${row.id}`}
                >
                  Add bonus
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Modal>
  );
}
