export type DateRangePreset = "all" | "7d" | "30d" | "90d" | "custom";
export type ReplyStatus = "all" | "replied" | "not_replied";
export type SentimentFilter = "all" | "positive" | "neutral" | "negative";

export interface ReportFilters {
  range: DateRangePreset;
  date_from: string | null;
  date_to: string | null;
  reply_status: ReplyStatus;
  sentiment: SentimentFilter;
}

export interface StoreReportRow {
  shop_id: number;
  shop_name: string;
  total_reviews: number;
  avg_rating: number;
  replied_count: number;
  not_replied_count: number;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
}

export type SortKey = keyof Omit<StoreReportRow, "shop_id" | "shop_name">;
export type SortDir = "asc" | "desc";
