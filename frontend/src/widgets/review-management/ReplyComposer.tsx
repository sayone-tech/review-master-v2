import { useState } from "react";
import { CheckCircle } from "lucide-react";
import { emitToast } from "../../lib/toast";
import { ApiError, submitReply } from "./api";
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
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const charCount = comment.length;
  const counterCls =
    charCount >= 3900 ? "text-[12px] text-red text-right mt-1" : "text-[12px] text-muted text-right mt-1";

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

  // Replied view — replaces composer after success.
  if (row.is_replied) {
    const replyDate = row.reply_update_time
      ? new Date(row.reply_update_time).toLocaleString()
      : "";
    return (
      <tr className="border-b border-line">
        <td colSpan={totalColumns} className="px-4 py-4 bg-line-soft">
          <div className="flex items-start gap-2">
            <CheckCircle size={20} className="text-green mt-0.5" aria-hidden="true" />
            <div className="flex-1">
              <div className="text-[14px] font-semibold text-ink">
                Replied on {replyDate}
              </div>
              <div className="text-[14px] text-text mt-1 whitespace-pre-wrap">
                {row.reply_comment}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-[12px] text-muted underline hover:text-ink"
            >
              Close
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-b border-line">
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
          <label
            htmlFor={`reply-textarea-${row.id}`}
            className="text-[12px] font-semibold text-subtle uppercase tracking-[0.05em] mb-2 block"
          >
            Your reply
          </label>
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
          <div className="flex items-center justify-end gap-2 mt-3">
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
      </td>
    </tr>
  );
}
