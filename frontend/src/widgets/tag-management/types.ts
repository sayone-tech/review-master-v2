// Phase 25-03 — Tag Management Widget types.

export type PolarityType = "always_positive" | "always_negative" | "mixed";

export interface OrgCanonicalTagRow {
  id: number;
  label: string;
  polarity_type: PolarityType;
  review_count: number;
  first_seen: string; // ISO date string
}

export type TagMergeJobStatus = "PENDING" | "IN_PROGRESS" | "SUCCESS" | "FAILED";

export interface TagMergeJobRow {
  id: number;
  status: TagMergeJobStatus;
  processed: number | null;
  total: number | null;
  source_label: string;
  target_label: string;
  error_message: string | null;
}

export interface PaginatedTagResponse {
  results: OrgCanonicalTagRow[];
  count: number;
  next: string | null;
  previous: string | null;
}

export interface FetchTagsParams {
  ordering?: string;
  page?: number;
  page_size?: number;
  search?: string;
}
