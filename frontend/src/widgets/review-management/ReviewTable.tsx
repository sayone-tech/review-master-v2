import { AlertCircle, Loader2, MessageCircle } from "lucide-react";
import type { ReactNode } from "react";
import { DataTable, type DataTableColumn } from "../data-table/DataTable";
import { ReplyComposer } from "./ReplyComposer";
import { StarRating } from "./StarRating";
import type { ReviewRow, TagPolarity } from "./types";

// Avatar colours — deterministically chosen from reviewer name hash
const AVATAR_PALETTE = [
  { bg: "#E0F2FE", fg: "#0369A1" },
  { bg: "#DCFCE7", fg: "#15803D" },
  { bg: "#FEF9C3", fg: "#A16207" },
  { bg: "#FCE7F3", fg: "#9D174D" },
  { bg: "#EDE9FE", fg: "#5B21B6" },
  { bg: "#FFEDD5", fg: "#C2410C" },
  { bg: "#F1F5F9", fg: "#475569" },
];

function hashName(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (name.charCodeAt(i) + ((h << 5) - h)) | 0;
  }
  return Math.abs(h);
}

function avatarPalette(name: string) {
  return AVATAR_PALETTE[hashName(name) % AVATAR_PALETTE.length];
}

function avatarInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function formatRelativeDate(iso: string): string {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 1) return "today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths === 1) return "1 month ago";
  if (diffMonths < 12) return `${diffMonths} months ago`;
  const diffYears = Math.floor(diffMonths / 12);
  return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
}

const TAG_STYLES: Record<TagPolarity, { backgroundColor: string; color: string }> = {
  positive: { backgroundColor: "#DCFCE7", color: "#15803D" },
  neutral: { backgroundColor: "#F4F4F5", color: "#52525B" },
  negative: { backgroundColor: "#FEE2E2", color: "#DC2626" },
};

const SENTIMENT_DOT: Record<string, { dot: string; label: string; bg: string; text: string }> = {
  positive: { dot: "#16A34A", label: "Positive", bg: "#F0FDF4", text: "#15803D" },
  neutral: { dot: "#9CA3AF", label: "Neutral", bg: "#F9FAFB", text: "#6B7280" },
  negative: { dot: "#DC2626", label: "Negative", bg: "#FEF2F2", text: "#B91C1C" },
};

// TOTAL_COLUMNS = 6 data columns, no actions column (must stay in sync with columns array below)
const TOTAL_COLUMNS = 6;

interface Props {
  rows: ReviewRow[];
  loading: boolean;
  emptyState: ReactNode;
  onReply: (row: ReviewRow) => void;
  expandedRowId: number | null;
  onComposerSuccess: (row: ReviewRow) => void;
  onComposerClose: () => void;
  showFullComment: Map<number, boolean>;
  onToggleShowFullComment: (reviewId: number) => void;
}

export function ReviewTable({
  rows,
  loading,
  emptyState,
  onReply,
  expandedRowId,
  onComposerSuccess,
  onComposerClose,
  showFullComment,
  onToggleShowFullComment,
}: Props) {
  const columns: DataTableColumn<ReviewRow>[] = [
    {
      key: "reviewer",
      label: "REVIEWER",
      skeletonWidth: "180px",
      accessor: (r) => {
        const name = r.reviewer_is_anonymous ? "Anonymous" : (r.reviewer_display_name || "—");
        const isAnon = r.reviewer_is_anonymous || !r.reviewer_display_name;
        const palette = isAnon ? { bg: "#F4F4F5", fg: "#52525B" } : avatarPalette(name);
        const initials = isAnon ? "?" : avatarInitials(name);
        const photoUrl = r.reviewer_photo_url && !r.reviewer_is_anonymous ? r.reviewer_photo_url : "";
        return (
          <div className="flex items-start gap-2.5 min-w-0">
            {photoUrl ? (
              <img
                src={photoUrl}
                alt=""
                referrerPolicy="no-referrer"
                className="w-8 h-8 rounded-full object-cover shrink-0 bg-line-soft"
                onError={(e) => {
                  // Hide broken image so the initials sibling can take over
                  const img = e.currentTarget;
                  img.style.display = "none";
                  const fallback = img.nextElementSibling as HTMLElement | null;
                  if (fallback) fallback.style.display = "flex";
                }}
              />
            ) : null}
            <span
              className="w-8 h-8 rounded-full items-center justify-center text-[12px] font-bold shrink-0"
              style={{
                backgroundColor: palette.bg,
                color: palette.fg,
                display: photoUrl ? "none" : "flex",
              }}
              aria-hidden="true"
            >
              {initials}
            </span>
            <div className="min-w-0">
              <div className="text-[13.5px] font-semibold text-ink leading-snug truncate max-w-[160px]">
                {name}
              </div>
              <div className="mt-0.5">
                <StarRating rating={r.star_rating} />
              </div>
              <div className="text-[11px] text-muted mt-0.5" title={r.review_create_time}>
                {formatRelativeDate(r.review_create_time)}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      key: "review",
      label: "REVIEW",
      skeletonWidth: "240px",
      accessor: (r) =>
        r.comment ? (
          <span className="text-[13.5px] text-text line-clamp-2 leading-snug max-w-[360px]">
            {r.comment}
          </span>
        ) : (
          <span className="text-[13px] text-muted italic">No comment left</span>
        ),
    },
    {
      key: "tags",
      label: "TAGS",
      skeletonWidth: "120px",
      accessor: (r) => {
        if (r.enrichment_status === "FAILED") {
          return (
            <span title="AI analysis failed" className="inline-flex items-center">
              <AlertCircle size={13} className="text-red" />
            </span>
          );
        }
        if (r.enrichment_status !== "SUCCESS") {
          return (
            <span className="inline-flex items-center gap-1 text-[11px] text-amber-600">
              <Loader2 size={11} className="animate-spin" aria-hidden="true" />
              Analyzing
            </span>
          );
        }
        if (!r.tags || r.tags.length === 0) {
          return <span className="text-muted text-[12px]">—</span>;
        }
        return (
          <div className="flex flex-wrap gap-1 max-w-[170px]">
            {r.tags.slice(0, 4).map((tag) => (
              <span
                key={`${tag.label}-${tag.polarity}`}
                className="inline-flex items-center px-1.5 py-0.5 text-[11px] font-medium rounded"
                style={TAG_STYLES[tag.polarity]}
              >
                {tag.label}
              </span>
            ))}
            {r.tags.length > 4 && (
              <span className="text-[11px] text-muted">+{r.tags.length - 4}</span>
            )}
          </div>
        );
      },
    },
    {
      key: "sentiment",
      label: "SENTIMENT",
      skeletonWidth: "80px",
      accessor: (r) => {
        if (r.enrichment_status === "FAILED") return null;
        if (r.enrichment_status !== "SUCCESS") return null;
        const s = SENTIMENT_DOT[r.sentiment] ?? SENTIMENT_DOT.neutral;
        return (
          <span
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[12px] font-semibold"
            style={{ backgroundColor: s.bg, color: s.text }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ backgroundColor: s.dot }}
              aria-hidden="true"
            />
            {s.label}
          </span>
        );
      },
    },
    {
      key: "shop",
      label: "SHOP",
      skeletonWidth: "120px",
      accessor: (r) => (
        <div>
          <div className="text-[13.5px] font-medium text-ink leading-snug">{r.shop_name}</div>
          {r.shop_region_name && (
            <div className="text-[11px] text-muted mt-0.5">{r.shop_region_name}</div>
          )}
        </div>
      ),
    },
    {
      key: "replies",
      label: "REPLIES",
      align: "right",
      skeletonWidth: "80px",
      accessor: (r) => {
        if (r.is_replied) {
          return (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold bg-line-soft text-ink">
              <MessageCircle size={12} aria-hidden="true" />
              1 reply
            </span>
          );
        }
        return (
          <button
            type="button"
            onClick={() => onReply(r)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[12px] font-semibold bg-yellow text-black hover:bg-yellow-hover"
          >
            <MessageCircle size={12} aria-hidden="true" />
            Reply
          </button>
        );
      },
    },
  ];

  const renderExpanded = (r: ReviewRow): ReactNode => {
    if (expandedRowId !== r.id) return null;
    const isFull = showFullComment.get(r.id) ?? false;
    return (
      <ReplyComposer
        row={r}
        totalColumns={TOTAL_COLUMNS}
        showFullComment={isFull}
        onToggleShowFullComment={() => onToggleShowFullComment(r.id)}
        onSuccess={onComposerSuccess}
        onClose={onComposerClose}
      />
    );
  };

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyState={emptyState}
      rowKey={(r) => String(r.id)}
      renderExpanded={renderExpanded}
      wrapperClassName="bg-white overflow-hidden"
    />
  );
}
