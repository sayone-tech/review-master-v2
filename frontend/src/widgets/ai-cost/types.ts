export type RangeKey = "this_month" | "last_month" | "7d" | "30d" | "90d" | "custom";

export interface CostFilters {
  range: RangeKey;
  from?: string;
  to?: string;
}

export type RequestTypeCosts = Record<string, string>;

export interface CostWindow {
  key: RangeKey;
  start: string;
  end: string;
}

export interface CostSummaryTotals {
  calls: number;
  success_calls: number;
  failed_calls: number;
  moderated_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  org_count: number;
  active_shops: number;
}

export interface CostSummaryResponse {
  range: CostWindow;
  generated_at: string;
  has_any_usage?: boolean;
  organisation?: { id: number; name: string; org_type: string; shop_count: number };
  totals: CostSummaryTotals;
}

export interface OrgCostRow {
  organisation_id: number;
  name: string;
  org_type: string;
  active_shops: number;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  by_request_type: RequestTypeCosts;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
  generated_at: string;
}

export type OrgListResponse = Paginated<OrgCostRow>;

export interface ShopCostRow {
  shop_id: number;
  name: string;
  region_name: string | null;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  by_request_type: RequestTypeCosts;
}

export interface UnattributedCost {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
  by_request_type: RequestTypeCosts;
}

export interface ShopListResponse extends Paginated<ShopCostRow> {
  unattributed: UnattributedCost | null;
}

export interface ModelCostRow {
  model: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: string;
}

export interface ModelListResponse {
  results: ModelCostRow[];
  generated_at: string;
}

export type OrgSortKey =
  | "name"
  | "active_shops"
  | "calls"
  | "input_tokens"
  | "output_tokens"
  | "cost";

export const PAGE_SIZES = [10, 25, 50, 100] as const;
