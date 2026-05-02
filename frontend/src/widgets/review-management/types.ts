export type EnrichmentStatus = "PENDING" | "IN_PROGRESS" | "SUCCESS" | "FAILED";
export type Sentiment = "" | "positive" | "neutral" | "negative";
export type TagPolarity = "positive" | "neutral" | "negative";

export interface ReviewTag {
  label: string;
  polarity: TagPolarity;
}

export type ActionItemScope = "shop" | "brand";
export type ActionItemPriority = "high" | "medium" | "low";

export interface ExtractedActionItem {
  title: string;
  scope: ActionItemScope;
  priority: ActionItemPriority;
}

export interface ReviewRow {
  id: number;
  shop_id: number;
  shop_name: string;
  shop_region_name: string;
  region_id: number | null;
  google_review_id: string;
  star_rating: 1 | 2 | 3 | 4 | 5;
  reviewer_display_name: string;
  reviewer_photo_url: string;
  reviewer_is_anonymous: boolean;
  comment: string;
  review_create_time: string;
  review_update_time: string;
  reply_comment: string;
  reply_update_time: string | null;
  is_replied: boolean;
  enrichment_status: EnrichmentStatus;
  sentiment: Sentiment;
  tags: ReviewTag[];
  extracted_action_items: ExtractedActionItem[];
  created_at: string;
  updated_at: string;
}

export type SortKey =
  | "-review_create_time"
  | "review_create_time"
  | "-star_rating"
  | "star_rating";

export interface ReviewFilterParams {
  shop?: number;
  rating?: 1 | 2 | 3 | 4 | 5;
  sentiment?: "positive" | "neutral" | "negative";
  is_replied?: boolean;
  from_date?: string; // YYYY-MM-DD
  to_date?: string; // YYYY-MM-DD
  search?: string;
  ordering?: SortKey;
  page_size?: 10 | 25 | 50 | 100;
  cursor?: string;
}

export interface ReviewListResponse {
  results: ReviewRow[];
  next: string | null;
  previous: string | null;
  total_count: number;
}

export interface SyncingShop {
  shop_id: number;
  shop_name: string;
}

export interface SyncingResponse {
  count: number;
  shops: SyncingShop[];
}

export interface ShopOption {
  id: number;
  name: string;
}
