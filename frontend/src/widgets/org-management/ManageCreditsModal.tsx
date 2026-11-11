import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Modal } from "../modal";
import { emitToast } from "../../lib/toast";
import {
  allocateBonus,
  CreditsApiError,
  isPeriodMismatch,
  type CreditPeriod,
  type CreditShopRow,
} from "./creditsApi";
import { formatCount, formatMonthYear } from "./creditHint";
import { useCreditShops } from "./useCreditShops";
import type { OrgRow } from "./types";

interface Props {
  org: OrgRow | null;
  onClose: () => void;
}

const AMOUNT_MIN = 1;
const AMOUNT_MAX = 10000;
const PAGE_SIZE = 10;
const HIGHLIGHT_MS = 3000;
const RANGE_ERROR = "Enter a whole number between 1 and 10,000.";

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
  const { data, loading, error, search, setSearch, page, setPage, reload } = useCreditShops(
    org?.id ?? null,
  );

  const [view, setView] = useState<"list" | "bonus">("list");
  const [shop, setShop] = useState<CreditShopRow | null>(null);
  const [bonusPeriod, setBonusPeriod] = useState<CreditPeriod>(currentUtcPeriod());
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [periodBanner, setPeriodBanner] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [amountError, setAmountError] = useState<string | null>(null);
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const [pendingFocusId, setPendingFocusId] = useState<number | null>(null);

  const amountRef = useRef<HTMLInputElement | null>(null);
  const rowButtons = useRef<Map<number, HTMLButtonElement>>(new Map());
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearHighlightTimer() {
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    highlightTimer.current = null;
  }

  // Reset to a clean list view when the modal opens for a (different) organisation.
  useEffect(() => {
    setView("list");
    setShop(null);
    setAmount("");
    setReason("");
    setSubmitting(false);
    setPeriodBanner(false);
    setRefreshing(false);
    setAmountError(null);
    setReasonError(null);
    setHighlightId(null);
    setPendingFocusId(null);
    clearHighlightTimer();
  }, [org?.id]);

  useEffect(() => clearHighlightTimer, []);

  useEffect(() => {
    if (view === "bonus") amountRef.current?.focus();
  }, [view]);

  // Move focus to the topped-up row once the refreshed list has rendered.
  useEffect(() => {
    if (pendingFocusId === null || view !== "list" || loading) return;
    rowButtons.current.get(pendingFocusId)?.focus();
    setPendingFocusId(null);
  }, [pendingFocusId, view, loading, data]);

  if (!org) return null;
  const currentOrg = org;

  const period = data?.period ?? currentUtcPeriod();
  const perShop = data?.allocation_per_shop ?? currentOrg.current_month_credit_allocation;
  const listSubtitle = `${currentOrg.name} — ${formatMonthYear(period.year, period.month)} · ${plural(perShop)} per shop`;

  const amountValue = parseAmount(amount);
  const clientAmountInvalid = amount.trim() !== "" && amountValue === null;
  const shownAmountError = clientAmountInvalid ? RANGE_ERROR : amountError;

  function openBonus(row: CreditShopRow) {
    clearHighlightTimer();
    setHighlightId(null);
    setShop(row);
    setBonusPeriod(period);
    setAmount("");
    setReason("");
    setAmountError(null);
    setReasonError(null);
    setPeriodBanner(false);
    setView("bonus");
  }

  function backToList() {
    if (submitting) return;
    setAmount("");
    setReason("");
    setAmountError(null);
    setReasonError(null);
    setPeriodBanner(false);
    setView("list");
  }

  function editAmount(v: string) {
    setAmount(v);
    setAmountError(null);
    setPeriodBanner(false);
  }

  function editReason(v: string) {
    setReason(v);
    setReasonError(null);
    setPeriodBanner(false);
  }

  function showGenericError() {
    emitToast({
      kind: "error",
      title: "Something went wrong.",
      msg: "Please try again. If the problem persists, contact support.",
    });
  }

  async function handleAllocate() {
    if (submitting || refreshing || amountValue === null || !shop) return;
    const target = shop;
    setSubmitting(true);
    setPeriodBanner(false);
    setAmountError(null);
    setReasonError(null);
    try {
      const trimmedReason = reason.trim();
      await allocateBonus(target.id, {
        amount: amountValue,
        period_year: bonusPeriod.year,
        period_month: bonusPeriod.month,
        ...(trimmedReason ? { reason: trimmedReason } : {}),
      });
      emitToast({ kind: "success", title: `Added ${plural(amountValue)} to ${target.name}.` });
      setAmount("");
      setReason("");
      setView("list");
      await reload();
      setHighlightId(target.id);
      setPendingFocusId(target.id);
      clearHighlightTimer();
      highlightTimer.current = setTimeout(() => setHighlightId(null), HIGHLIGHT_MS);
    } catch (err) {
      if (isPeriodMismatch(err)) {
        // D-12: swap in the server's month and balance, keep the typed values and
        // require a fresh Allocate click (never auto-resubmit).
        const { balance, period: serverPeriod } = err.body;
        setPeriodBanner(true);
        setRefreshing(true);
        setShop({
          ...target,
          allocated: balance.allocated,
          bonus: balance.bonus,
          consumed: balance.consumed,
          remaining: balance.remaining,
        });
        setBonusPeriod(serverPeriod);
        try {
          await reload();
        } finally {
          setRefreshing(false);
        }
      } else if (err instanceof CreditsApiError && err.status === 404) {
        emitToast({
          kind: "error",
          title: "This shop is no longer active.",
          msg: "The list has been refreshed.",
        });
        setAmount("");
        setReason("");
        setView("list");
        await reload();
      } else if (err instanceof CreditsApiError && err.status === 400) {
        const fields = (err.body ?? {}) as Record<string, unknown>;
        const first = (v: unknown) => (Array.isArray(v) && typeof v[0] === "string" ? v[0] : null);
        const amountMsg = first(fields.amount);
        const reasonMsg = first(fields.reason);
        if (amountMsg || reasonMsg) {
          setAmountError(amountMsg);
          setReasonError(reasonMsg);
        } else {
          showGenericError();
        }
      } else {
        showGenericError();
      }
    } finally {
      setSubmitting(false);
    }
  }

  const rows = data?.results ?? [];
  const count = data?.count ?? 0;
  const showSkeleton = loading || (!data && !error);
  const showError = error && !loading;
  const showEmpty = !showSkeleton && !showError && data !== null && count === 0;
  const trimmedSearch = search.trim();
  const rangeStart = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, count);

  const listBody = (
    <>
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
        aria-busy={showSkeleton}
        data-testid="credits-list"
      >
        {showSkeleton && (
          <div>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 animate-sk-pulse border-b border-line-soft last:border-b-0" />
            ))}
          </div>
        )}
        {showError && (
          <div className="bg-red-tint text-[#991B1B] px-4 py-8 text-center">
            <p className="text-[14px] font-semibold">Couldn't load shops.</p>
            <p className="text-[12px] mt-1">
              Please try again. If the problem persists, contact support.
            </p>
            <button
              type="button"
              onClick={() => void reload()}
              className={`${secondaryBtn} h-8 px-4 text-[13px] mt-4`}
            >
              Retry
            </button>
          </div>
        )}
        {showEmpty && (
          <div className="px-4 py-8 text-center">
            {trimmedSearch ? (
              <>
                <p className="text-[14px] font-semibold text-ink break-words">
                  {`No shops match "${trimmedSearch}"`}
                </p>
                <p className="text-[12px] text-muted mt-1">
                  Check the spelling or try a shorter name.
                </p>
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className={`${secondaryBtn} h-8 px-4 text-[13px] mt-4`}
                >
                  Clear search
                </button>
              </>
            ) : (
              <>
                <p className="text-[14px] font-semibold text-ink">No active shops</p>
                <p className="text-[12px] text-muted mt-1">
                  This organisation has no active shops yet. Shops added by its Org Admin will
                  appear here.
                </p>
              </>
            )}
          </div>
        )}
        {!showSkeleton && !showError && rows.length > 0 && (
          <ul>
            {rows.map((row) => (
              <li
                key={row.id}
                data-testid={`credits-row-${row.id}`}
                className={`px-4 py-4 border-b border-line-soft last:border-b-0 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4 ${
                  highlightId === row.id ? "bg-yellow-tint" : ""
                }`}
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
                    ref={(el) => {
                      if (el) rowButtons.current.set(row.id, el);
                      else rowButtons.current.delete(row.id);
                    }}
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
        )}
        {data && !showError && (
          <div className="px-4 py-2 border-t border-line bg-[#FBFBFB] text-[13px] text-muted flex items-center justify-between">
            <span aria-live="polite">
              {count === 0 ? "No results" : `Showing ${rangeStart}–${rangeEnd} of ${count}`}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className={`h-8 w-8 rounded-sm bg-white border border-line inline-flex items-center justify-center ${
                  page <= 1 ? "opacity-40 cursor-not-allowed" : "hover:bg-line-soft"
                }`}
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Next page"
                disabled={page * PAGE_SIZE >= count}
                onClick={() => setPage(page + 1)}
                className={`h-8 w-8 rounded-sm bg-white border border-line inline-flex items-center justify-center ${
                  page * PAGE_SIZE >= count ? "opacity-40 cursor-not-allowed" : "hover:bg-line-soft"
                }`}
              >
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );

  const listFooter = (
    <button
      type="button"
      onClick={onClose}
      className={`${secondaryBtn} h-10 px-4 text-[14px]`}
      data-testid="credits-close"
    >
      Close
    </button>
  );

  const allocateDisabled = amountValue === null || submitting || refreshing;
  const stat = (value: number) =>
    refreshing ? (
      <span className="block h-5 w-12 rounded-sm bg-line animate-sk-pulse" />
    ) : (
      formatCount(value)
    );

  const bonusBody = shop && (
    <>
      {periodBanner && (
        <p
          className="mb-4 bg-amber-tint text-[#92400E] px-4 py-2 rounded-md text-[12px]"
          role="alert"
          data-testid="credits-period-banner"
        >
          A new month started — balances have been refreshed. Review and try again.
        </p>
      )}
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
            <dd className="text-[14px] font-semibold text-ink">{stat(value)}</dd>
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
          onChange={(e) => editAmount(e.target.value)}
          placeholder="e.g. 50"
          aria-invalid={shownAmountError ? true : undefined}
          className={`${inputCls} ${shownAmountError ? "border-red" : ""}`}
          data-testid="credits-amount"
        />
        {shownAmountError ? (
          <p className="mt-1 text-[12px] text-red" role="alert">
            {shownAmountError}
          </p>
        ) : (
          <p className="mt-1 text-[12px] text-muted">Whole number from 1 to 10,000.</p>
        )}
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
            <span className="text-ink font-semibold">{formatCount(shop.bonus + amountValue)}</span>
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
          onChange={(e) => editReason(e.target.value)}
          placeholder="e.g. Goodwill credit after outage"
          aria-invalid={reasonError ? true : undefined}
          className={`${inputCls} ${reasonError ? "border-red" : ""}`}
          data-testid="credits-reason"
        />
        {reasonError && (
          <p className="mt-1 text-[12px] text-red" role="alert">
            {reasonError}
          </p>
        )}
      </div>
    </>
  );

  const bonusFooter = (
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
        disabled={allocateDisabled}
        className={`inline-flex items-center justify-center gap-2 bg-yellow text-black border border-yellow-hover hover:bg-yellow-hover rounded-md h-10 px-4 text-[14px] font-semibold ${
          allocateDisabled ? "opacity-50 cursor-not-allowed pointer-events-none" : ""
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
  );

  const inBonus = view === "bonus" && shop !== null;
  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={inBonus ? "Add Bonus Credits" : "Manage Credits"}
      subtitle={
        inBonus && shop
          ? `${shop.name} — ${formatMonthYear(bonusPeriod.year, bonusPeriod.month)}`
          : listSubtitle
      }
      footer={inBonus ? bonusFooter : listFooter}
    >
      {inBonus ? bonusBody : listBody}
    </Modal>
  );
}
