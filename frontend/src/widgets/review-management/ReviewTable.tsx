import { MoreHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import { ReplyStatusBadge } from "./ReplyStatusBadge";
import { SentimentBadge } from "./SentimentBadge";
import { StarRating } from "./StarRating";
import type { ReviewRow } from "./types";

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths === 1) return "1 month ago";
  return `${diffMonths} months ago`;
}

interface Props {
  rows: ReviewRow[];
  loading: boolean;
  emptyState: ReactNode;
  onReply: (row: ReviewRow) => void;
  expandedRowId: number | null;
  expandedRow: ReactNode;
  // REVW-06 — passed from widget; consumed by Plan 11's ComposerAwareRow.
  showFullComment: Map<number, boolean>;
  onToggleShowFullComment: (reviewId: number) => void;
}

export function ReviewTable({
  rows,
  loading,
  emptyState,
  onReply,
  expandedRowId,
  expandedRow,
  // showFullComment + onToggleShowFullComment are accepted here for the Plan 11
  // wiring; in Plan 10 the table only uses DataTable so they pass through unused.
  showFullComment: _showFullComment,
  onToggleShowFullComment: _onToggleShowFullComment,
}: Props) {
  const columns: DataTableColumn<ReviewRow>[] = [
    {
      key: "rating",
      label: "RATING",
      skeletonWidth: "80px",
      accessor: (r) => <StarRating rating={r.star_rating} />,
    },
    {
      key: "shop",
      label: "SHOP",
      skeletonWidth: "120px",
      accessor: (r) => (
        <div>
          <div className="text-[14px] text-ink font-semibold">{r.shop_name}</div>
          {r.shop_region_name && (
            <div className="text-[12px] text-muted">{r.shop_region_name}</div>
          )}
        </div>
      ),
    },
    {
      key: "reviewer",
      label: "REVIEWER",
      skeletonWidth: "120px",
      accessor: (r) =>
        r.reviewer_is_anonymous ? (
          <span className="text-muted">Anonymous</span>
        ) : (
          <span className="text-[14px] text-ink">{r.reviewer_display_name || "—"}</span>
        ),
    },
    {
      key: "date",
      label: "DATE",
      skeletonWidth: "80px",
      accessor: (r) => (
        <span className="text-[14px] text-text" title={r.review_create_time}>
          {formatRelativeDate(r.review_create_time)}
        </span>
      ),
    },
    {
      key: "sentiment",
      label: "SENTIMENT",
      skeletonWidth: "80px",
      accessor: (r) => (
        <SentimentBadge sentiment={r.sentiment} enrichmentStatus={r.enrichment_status} />
      ),
    },
    {
      key: "reply_status",
      label: "REPLY",
      skeletonWidth: "80px",
      accessor: (r) => <ReplyStatusBadge isReplied={r.is_replied} />,
    },
    {
      key: "reply_cta",
      label: "",
      skeletonWidth: "80px",
      accessor: (r) =>
        r.is_replied ? null : (
          <button
            type="button"
            className="bg-yellow text-black text-[12px] font-semibold px-3 py-1 rounded-md hover:bg-yellow-hover"
            onClick={() => onReply(r)}
          >
            Reply
          </button>
        ),
    },
  ];

  return (
    <div data-testid="review-table-wrap">
      <DataTable
        columns={columns}
        rows={rows}
        loading={loading}
        emptyState={emptyState}
        rowKey={(r) => String(r.id)}
        renderRowActions={(_r) => (
          <button
            type="button"
            aria-label="More actions for this review"
            className="w-8 h-8 rounded-md text-muted hover:bg-line-soft hover:text-ink flex items-center justify-center"
          >
            <MoreHorizontal size={14} aria-hidden="true" />
          </button>
        )}
      />
      {/* Plan 11 will render the inline composer for the row matching expandedRowId */}
      {expandedRowId !== null && expandedRow}
    </div>
  );
}
