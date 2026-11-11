import { useState, useEffect, useRef } from "react";
import { CheckCircle, ChevronDown, Loader2, Sparkles, Trash2 } from "lucide-react";
import { emitToast } from "../../lib/toast";
import {
  ApiError,
  deleteReply,
  generateReply,
  getCreditCost,
  readInsufficientCredits,
  submitReply,
} from "./api";
import { setShopCredits, useShopCredits } from "../credits/creditsStore";
import { creditsLabel } from "../credits/format";
import { readCreditContact } from "../credits/contact";
import { BuyMoreCreditsModal } from "../credits/BuyMoreCreditsModal";
import { formatCount } from "../org-management/creditHint";
import { listTemplates } from "../reply-templates/api";
import type { TemplateRow } from "../reply-templates/types";
import { StarRating } from "./StarRating";
import type { ReviewRow } from "./types";

interface Props {
  row: ReviewRow;
  totalColumns: number;
  // REVW-06 — wired from ReviewManagementWidget via ReviewTable's renderExpanded.
  showFullComment: boolean;
  onToggleShowFullComment: () => void;
  onSuccess: (updated: ReviewRow) => void;
  onClose: () => void;
}

export function ReplyComposer({
  row, totalColumns, showFullComment, onToggleShowFullComment, onSuccess, onClose,
}: Props) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [generatingTone, setGeneratingTone] = useState<"professional" | "friendly" | null>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const generatorButtonRef = useRef<HTMLButtonElement>(null);
  // IN-04: track the active generate-reply AbortController so we can cancel
  // an in-flight request when the user re-clicks a different tone or the
  // composer unmounts mid-generation.
  const generateAbortRef = useRef<AbortController | null>(null);

  // CVIS-03 — the cost always comes from the server (never derived client-side).
  const hasReviewText = row.comment.trim() !== "";
  const [cost, setCost] = useState<number | null>(null);
  const [costStatus, setCostStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const credits = useShopCredits(row.shop_id);
  const [costAttempt, setCostAttempt] = useState(0);
  const [buyMoreOpen, setBuyMoreOpen] = useState(false);
  const creditContact = readCreditContact();

  // Fetch the credit cost on mount. AbortController keeps this StrictMode-safe
  // (effects mount twice in dev) and cancels on unmount.
  useEffect(() => {
    if (!hasReviewText || row.is_replied) return;
    const controller = new AbortController();
    setCostStatus("loading");
    getCreditCost(row.id, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) return;
        setCost(res.cost);
        setCostStatus("ready");
        setShopCredits(row.shop_id, { remaining: res.remaining, isEnabled: res.is_enabled });
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        setCostStatus("error");
      });
    return () => controller.abort();
  }, [row.id, row.shop_id, row.is_replied, hasReviewText, costAttempt]);

  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => {});
  }, []);

  // IN-04: abort any pending generate-reply request when the composer unmounts.
  useEffect(() => {
    return () => {
      generateAbortRef.current?.abort();
      generateAbortRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!pickerOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [pickerOpen]);

  // UI-SPEC Interaction C: one credit state at a time. The store entry wins for
  // `remaining` / `isEnabled`; the cost only ever comes from the server.
  type CreditUiState = "none" | "loading" | "ready" | "not_enabled" | "insufficient" | "load_error";
  let creditState: CreditUiState;
  if (!hasReviewText) creditState = "none";
  else if (costStatus === "error") creditState = "load_error";
  else if (costStatus !== "ready" || !credits) creditState = "loading";
  else if (!credits.isEnabled) creditState = "not_enabled";
  else if (cost !== null && credits.remaining < cost) creditState = "insufficient";
  else creditState = "ready";

  const showCostSuffix = (creditState === "ready" || creditState === "insufficient") && cost !== null;
  const aiButtonLabel = showCostSuffix
    ? `Generate with AI · ${creditsLabel(cost as number)}`
    : "Generate with AI";
  const aiButtonDisabled =
    creditState === "loading" || creditState === "not_enabled" || creditState === "insufficient";

  let creditStatusText = "";
  if (creditState === "loading") creditStatusText = "Checking credits…";
  else if (creditState === "ready" && credits)
    creditStatusText = `This shop has ${creditsLabel(credits.remaining)} remaining this month.`;
  else if (creditState === "not_enabled") creditStatusText = "AI replies aren't enabled for this shop.";
  else if (creditState === "insufficient" && credits && cost !== null)
    creditStatusText = `Not enough credits — this reply needs ${formatCount(cost)}, you have ${formatCount(credits.remaining)}.`;
  else if (creditState === "load_error") creditStatusText = "Couldn't check your credit balance.";

  const charCount = comment.length;
  const counterCls =
    charCount >= 3900 ? "text-[12px] text-red text-right mt-1" : "text-[12px] text-muted text-right mt-1";

  const handleToggleGenerator = () => {
    setGeneratorOpen((o) => !o);
    if (generatorOpen) {
      // Closing: reset generating state too
      setGeneratingTone(null);
    }
  };

  const handleCancelGenerator = () => {
    setGeneratorOpen(false);
    setGeneratingTone(null);
    generatorButtonRef.current?.focus();
  };

  const handleGenerate = async (tone: "professional" | "friendly") => {
    // IN-04: cancel any in-flight request so a fast re-click doesn't race.
    generateAbortRef.current?.abort();
    const controller = new AbortController();
    generateAbortRef.current = controller;

    setGeneratingTone(tone);
    setErrorMessage(null);
    try {
      const { draft, credits_remaining } = await generateReply(row.id, tone, controller.signal);
      if (controller.signal.aborted) return;
      // D-05: the shop-keyed store updates every composer's line without a reload.
      setShopCredits(row.shop_id, { remaining: credits_remaining });
      setComment(draft);
      setGeneratorOpen(false);
      setGeneratingTone(null);
      document.getElementById(`reply-textarea-${row.id}`)?.focus();
    } catch (e) {
      // Swallow AbortError — the user (or a newer click) cancelled.
      if (controller.signal.aborted) return;
      if (e instanceof DOMException && e.name === "AbortError") return;
      setGeneratorOpen(false);
      setGeneratingTone(null);

      // D-08: a 402 is a state change, not an error. Adopt the server's numbers
      // (not stale local ones), keep the draft exactly as typed, show no banner.
      const insufficient = readInsufficientCredits(e);
      if (insufficient) {
        setShopCredits(row.shop_id, {
          remaining: insufficient.remaining,
          isEnabled: insufficient.reason !== "not_enabled",
        });
        if (insufficient.reason === "exhausted") setCost(insufficient.required);
        setCostStatus("ready");
        document.getElementById(`reply-textarea-${row.id}`)?.focus();
        return;
      }

      // 422 / 502 carry the shop's balance; a null credits_remaining is ignored by the store.
      if (e instanceof ApiError && (e.status === 422 || e.status === 502)) {
        const remaining = (e.data as { credits_remaining?: unknown } | null)?.credits_remaining;
        if (typeof remaining === "number") setShopCredits(row.shop_id, { remaining });
      }

      let message = "AI generation failed. Please try again or write your reply manually.";
      if (e instanceof ApiError && e.status === 409 && (e.data as { code?: string } | null)?.code === "generation_in_progress") {
        message = "A reply is already being generated for this review. Please wait a moment.";
      } else if (e instanceof ApiError && e.status === 422 && typeof e.data === "object" && e.data && (e.data as { code?: string }).code === "content_moderated") {
        message = (e.data as { detail?: string }).detail ?? "AI reply isn't available for this review. Please write your reply manually.";
      } else if (e instanceof ApiError && e.status === 429) {
        if (typeof e.retryAfterSeconds === "number" && e.retryAfterSeconds > 0) {
          message = `You've reached the AI generation limit. Please try again in ${e.retryAfterSeconds} seconds.`;
        } else {
          message = "You've reached the AI generation limit. Please wait a moment.";
        }
      }
      setErrorMessage(message);
      generatorButtonRef.current?.focus();
    } finally {
      if (generateAbortRef.current === controller) {
        generateAbortRef.current = null;
      }
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const updated = await submitReply(row.id, comment);
      emitToast({ kind: "success", title: "Reply posted." });
      onSuccess(updated);
    } catch (e) {
      let message = "Failed to post reply. Please try again.";
      if (e instanceof ApiError) {
        if (e.status === 429) {
          message = "You're replying too quickly. Please wait a moment.";
        } else if (e.status === 409) {
          message = "Another reply submission is in progress. Please wait.";
        } else if (e.status === 502 && typeof e.data === "object" && e.data) {
          const code = (e.data as { code?: string }).code;
          if (code === "invalid_grant") {
            message = "Google connection expired. Reconnect Google in Shops.";
          } else if (code === "reply_rejected") {
            message = "Google rejected the reply. Please review the content and try again.";
          } else if (code === "unreachable") {
            message = "Google is temporarily unavailable. Please try again.";
          }
        }
      }
      setErrorMessage(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setErrorMessage(null);
    try {
      const updated = await deleteReply(row.id);
      emitToast({ kind: "success", title: "Reply deleted." });
      onSuccess(updated);
    } catch (e) {
      let message = "Failed to delete reply. Please try again.";
      if (e instanceof ApiError) {
        if (e.status === 409) message = "Another operation is in progress. Please wait.";
        else if (e.status === 502 && typeof e.data === "object" && e.data) {
          const code = (e.data as { code?: string }).code;
          if (code === "invalid_grant") message = "Google connection expired. Reconnect Google in Shops.";
          else if (code === "unreachable") message = "Google is temporarily unavailable. Please try again.";
        }
      }
      setErrorMessage(message);
      setConfirmDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  // Replied view — replaces composer after success.
  if (row.is_replied) {
    const replyDate = row.reply_update_time
      ? new Date(row.reply_update_time).toLocaleString()
      : "";
    return (
      <tr id={`composer-row-${row.id}`} className="border-b border-line">
        <td colSpan={totalColumns} className="px-4 py-4 bg-line-soft">
          <div className="flex items-start gap-2">
            <CheckCircle size={20} className="text-green mt-0.5" aria-hidden="true" />
            <div className="flex-1">
              <div>
                <div className="text-[14px] font-semibold text-ink">
                  Replied on {replyDate}
                </div>
                {row.replied_by_name && (
                  <div className="text-[12px] text-subtle mt-0.5">
                    by {row.replied_by_name}
                  </div>
                )}
              </div>
              <div className="text-[14px] text-text mt-1 whitespace-pre-wrap">
                {row.reply_comment}
              </div>
            </div>
            <div className="flex flex-col items-end gap-2 shrink-0">
              {confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-[12px] text-red">Delete this reply?</span>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="text-[12px] font-semibold text-red hover:underline disabled:opacity-50"
                  >
                    {deleting ? "Deleting…" : "Confirm"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    disabled={deleting}
                    className="text-[12px] text-muted hover:text-ink"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className="inline-flex items-center gap-1 text-[12px] text-muted hover:text-red transition-colors"
                  title="Delete reply"
                >
                  <Trash2 size={13} aria-hidden="true" />
                  Delete reply
                </button>
              )}
              {errorMessage && (
                <p className="text-[12px] text-red text-right">{errorMessage}</p>
              )}
              <button
                type="button"
                onClick={onClose}
                className="text-[12px] text-muted underline hover:text-ink"
              >
                Close
              </button>
            </div>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr id={`composer-row-${row.id}`} className="border-b border-line">
      <td colSpan={totalColumns} className="p-0">
        <div className="px-4 py-3 bg-line-soft border-b border-line">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[14px] font-semibold text-ink">
              {row.reviewer_is_anonymous ? "Anonymous" : row.reviewer_display_name}
            </span>
            <StarRating rating={row.star_rating} />
            <span className="text-[12px] text-muted">{row.shop_name}</span>
            <span
              className="text-[12px] text-muted"
              title={row.review_create_time}
            >
              {new Date(row.review_create_time).toLocaleDateString()}
            </span>
          </div>
          {/* REVW-06 — truncate at 1000 chars with Show more / Show less toggle. */}
          {row.comment.length > 1000 && !showFullComment ? (
            <div className="text-[14px] text-text whitespace-pre-wrap">
              {row.comment.slice(0, 1000)}…{" "}
              <button
                type="button"
                onClick={onToggleShowFullComment}
                className="text-[12px] text-muted underline hover:text-ink"
              >
                Show more
              </button>
            </div>
          ) : (
            <div className="text-[14px] text-text whitespace-pre-wrap">
              {row.comment}
              {row.comment.length > 1000 && (
                <>
                  {" "}
                  <button
                    type="button"
                    onClick={onToggleShowFullComment}
                    className="text-[12px] text-muted underline hover:text-ink"
                  >
                    Show less
                  </button>
                </>
              )}
            </div>
          )}
        </div>
        <div className="px-4 py-4">
          {creditState !== "none" && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
              <p
                id={`credit-status-${row.id}`}
                role="status"
                aria-live="polite"
                className={`text-[12px] ${creditState === "insufficient" ? "text-[#92400E]" : "text-muted"}`}
              >
                {creditStatusText}
              </p>
              {creditState === "load_error" && (
                <button
                  type="button"
                  data-testid={`credit-retry-${row.id}`}
                  onClick={() => setCostAttempt((n) => n + 1)}
                  className="text-[12px] font-semibold text-ink underline underline-offset-2 hover:text-muted"
                >
                  Retry Credit Check
                </button>
              )}
            </div>
          )}
          <div className="flex items-center justify-between mb-2">
            <label
              htmlFor={`reply-textarea-${row.id}`}
              className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em]"
            >
              Your reply
            </label>
            <div className="flex items-center gap-2">
              {hasReviewText && (
                <button
                  ref={generatorButtonRef}
                  type="button"
                  aria-label={aiButtonLabel}
                  aria-expanded={generatorOpen}
                  aria-controls={`ai-generator-${row.id}`}
                  aria-busy={creditState === "loading" ? true : undefined}
                  aria-describedby={`credit-status-${row.id}`}
                  disabled={aiButtonDisabled}
                  onClick={handleToggleGenerator}
                  className={`inline-flex items-center gap-1 px-2 py-1 text-[12px] font-semibold border border-line rounded-md text-ink transition-colors disabled:bg-line-soft disabled:text-subtle disabled:cursor-not-allowed ${generatorOpen ? "bg-line-soft hover:bg-line" : "bg-white hover:bg-line-soft"}`}
                >
                  <Sparkles size={12} aria-hidden="true" />
                  {aiButtonLabel}
                </button>
              )}
              {templates.length > 0 && (
                <div ref={pickerRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setPickerOpen((o) => !o)}
                    className="inline-flex items-center gap-1 px-2 py-1 text-[12px] font-semibold border border-line rounded-md text-ink bg-white hover:bg-line-soft transition-colors"
                  >
                    Use template
                    <ChevronDown size={12} aria-hidden="true" />
                  </button>
                  {pickerOpen && (
                    <div className="absolute right-0 z-20 mt-1 w-64 bg-white border border-line rounded-md shadow-lg overflow-hidden">
                      <ul role="listbox" aria-label="Reply templates" className="max-h-56 overflow-y-auto py-1">
                        {templates.map((t) => (
                          <li key={t.id}>
                            <button
                              type="button"
                              role="option"
                              aria-selected={false}
                              onClick={() => {
                                setComment(t.content);
                                setPickerOpen(false);
                              }}
                              className="w-full text-left px-3 py-2 hover:bg-line-soft transition-colors"
                            >
                              <div className="text-[13px] font-semibold text-ink truncate">{t.name}</div>
                              <div className="text-[12px] text-muted truncate mt-1">{t.content.slice(0, 60)}{t.content.length > 60 ? "…" : ""}</div>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          {generatorOpen && (
            <div
              id={`ai-generator-${row.id}`}
              className={`flex items-center gap-2 mb-2${comment.trim() !== "" ? " flex-wrap" : ""}`}
              role="group"
              aria-label={comment.trim() === "" ? "Select tone for AI reply" : "Confirm replacing draft with AI reply"}
            >
              {comment.trim() !== "" && (
                <span className="text-[12px] text-muted">Replace your draft with AI reply?</span>
              )}
              {(["professional", "friendly"] as const).map((tone) => {
                const isLoading = generatingTone === tone;
                const isDisabled = generatingTone !== null;
                const label = tone === "professional" ? "Professional" : "Friendly";
                // D-06: once a draft exists the pill shows what a replacement costs.
                const showPillCost = comment.trim() !== "" && cost !== null;
                const ariaLabel = isLoading
                  ? `Generating ${label} reply…`
                  : showPillCost
                    ? `Generate ${label} reply, ${creditsLabel(cost as number)}`
                    : `Generate ${label} reply`;
                if (isLoading) {
                  return (
                    <button
                      key={tone}
                      type="button"
                      disabled
                      aria-busy="true"
                      aria-label={ariaLabel}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[12px] font-semibold border border-line rounded-md bg-line-soft text-faint cursor-not-allowed"
                    >
                      <Loader2 size={12} className="animate-spin text-amber" aria-hidden="true" />
                      {label}…
                    </button>
                  );
                }
                return (
                  <button
                    key={tone}
                    type="button"
                    onClick={() => handleGenerate(tone)}
                    disabled={isDisabled}
                    aria-busy={generatingTone === tone}
                    aria-label={ariaLabel}
                    className="inline-flex items-center gap-1 px-2 py-1 text-[12px] font-semibold border border-line rounded-md bg-white text-ink hover:bg-amber-tint hover:text-amber hover:border-amber transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-ink disabled:hover:border-line"
                  >
                    {showPillCost ? `${label} · ${formatCount(cost as number)} cr` : label}
                  </button>
                );
              })}
              {comment.trim() !== "" && (
                <button
                  type="button"
                  onClick={handleCancelGenerator}
                  className="text-[12px] font-semibold text-muted hover:text-ink transition-colors"
                  aria-label="Cancel AI reply generation"
                >
                  Cancel
                </button>
              )}
            </div>
          )}
          <textarea
            id={`reply-textarea-${row.id}`}
            className="w-full min-h-[120px] px-3 py-2 text-[14px] bg-white border border-line rounded-md focus:outline-none focus:ring focus:ring-black/[0.06] focus:border-ink resize-y"
            maxLength={4000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            aria-label="Write your reply"
            aria-describedby={`char-counter-${row.id}`}
            disabled={submitting}
          />
          <div
            id={`char-counter-${row.id}`}
            className={counterCls}
            aria-live="polite"
          >
            {charCount} / 4000
          </div>
          {errorMessage && (
            <div
              role="alert"
              className="border-l-4 border-red bg-red-tint px-4 py-2 text-[14px] text-red rounded-sm mt-2"
            >
              {errorMessage}
            </div>
          )}
          <div className="flex items-center justify-between gap-2 mt-3">
            {creditState === "insufficient" ? (
              <button
                type="button"
                data-testid={`credit-buy-more-${row.id}`}
                onClick={() => setBuyMoreOpen(true)}
                className="inline-flex h-8 items-center text-[12px] font-semibold text-ink underline underline-offset-2 hover:text-muted"
              >
                Buy More Credits
              </button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="bg-white text-ink border border-line hover:bg-line-soft px-4 py-2 text-[14px] font-semibold rounded-md disabled:opacity-50"
              >
                Discard Reply
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || comment.trim().length === 0}
                className="bg-yellow text-black hover:bg-yellow-hover px-4 py-2 text-[14px] font-semibold rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Submitting…" : "Submit Reply"}
              </button>
            </div>
          </div>
          {buyMoreOpen && (
            <BuyMoreCreditsModal
              open
              onClose={() => setBuyMoreOpen(false)}
              organisationName={creditContact.organisationName}
              supportEmail={creditContact.supportEmail}
              shop={{
                name: row.shop_name,
                remaining: credits?.remaining,
                total: credits?.total,
                isEnabled: credits?.isEnabled,
                periodLabel: credits?.periodLabel,
              }}
            />
          )}
        </div>
      </td>
    </tr>
  );
}
