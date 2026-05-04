// Phase 13 Plan 07 — Source Review tab (ACTN-11).
// Read-only review snippet + "Open in Reviews" deep link. Visible only when
// the parent action item has source=AI and source_review is non-null.
import { Star } from "lucide-react";
import type { SourceReviewSnippet } from "./types";

interface Props {
  review: SourceReviewSnippet;
  reviewId: number;
}

function StarRow({ rating }: { rating: number }) {
  const stars = Math.max(1, Math.min(5, Math.round(rating))) as 1 | 2 | 3 | 4 | 5;
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label={`${stars} out of 5 stars`}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          size={14}
          className={n <= stars ? "text-yellow" : "text-line"}
          fill={n <= stars ? "#FACC15" : "none"}
          aria-hidden="true"
        />
      ))}
    </span>
  );
}

export function SourceReviewTab({ review, reviewId }: Props) {
  return (
    <div className="p-4 space-y-3">
      <div className="bg-line-soft rounded-card p-4 space-y-2">
        <div className="flex items-center gap-3">
          <span className="text-[14px] font-semibold text-ink">
            {review.reviewer_name || "Anonymous"}
          </span>
          <StarRow rating={review.rating} />
        </div>
        <div className="text-[14px] text-ink whitespace-pre-wrap">
          {review.comment || <span className="italic text-muted">No comment left</span>}
        </div>
      </div>
      <a
        href={`/admin/org/reviews/?id=${reviewId}`}
        className="text-[14px] text-yellow underline hover:opacity-80 inline-block"
      >
        Open in Reviews
      </a>
    </div>
  );
}
