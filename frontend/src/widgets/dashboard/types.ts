export interface Region {
  id: number;
  name: string;
}

export interface Shop {
  id: number;
  name: string;
  region_id: number | null;
}

export type DateRangePreset = "all" | "7d" | "30d" | "90d" | "custom";

export interface DashboardFilters {
  region_id: number | null;
  shop_id: number | null;
  range: DateRangePreset;
  date_from: string | null; // ISO YYYY-MM-DD; computed for presets, user-supplied for custom
  date_to: string | null;
}

export interface KpisResponse {
  total_reviews: number;
  avg_rating: number;
  negative_reviews: number;
  negative_pct: number;
  enriched_count: number;
  store_count: number;
}

export interface SentimentResponse {
  positive: number;
  neutral: number;
  negative: number;
  enriched_count: number;
  total_count: number;
  coverage_pct: number;
}

export interface TopPerformingShop {
  shop_id: number;
  shop_name: string;
  review_count: number;
  avg_rating: number;
}

export interface TopPerformingResponse {
  shops: TopPerformingShop[];
  split: boolean;
}

export interface HighlightShop {
  shop_id: number;
  shop_name: string;
  avg_rating: number;
  positive_count: number;
  negative_count: number;
  review_count: number;
}

export interface HighlightsResponse {
  top: HighlightShop | null;
  bottom: HighlightShop | null;
}

export interface YourStoreResponse {
  shop_id: number;
  shop_name: string;
  region_name: string | null;
  avg_rating: number;
  total_reviews: number;
  positive_count: number;
  positive_pct: number;
  negative_count: number;
  negative_pct: number;
  distribution: { 1: number; 2: number; 3: number; 4: number; 5: number };
  trend_direction: "up" | "down" | "flat" | "none";
  trend_delta: number | null;
}

export interface DashboardBootstrap {
  regions: Region[];
  shops: Shop[];
  isSingleShop: boolean;
}
