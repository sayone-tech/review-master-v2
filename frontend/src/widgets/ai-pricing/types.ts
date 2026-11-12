export type PriceStatus = "current" | "scheduled" | "historical";
export type PriceSource = "manual" | "sync" | "seed";

export interface PriceRow {
  id: number;
  model: string;
  input_token_price_per_1m: string;
  output_token_price_per_1m: string;
  cached_token_price_per_1m: string;
  effective_from: string;
  effective_to: string | null;
  source: PriceSource;
  created_by: { id: number; name?: string; email?: string } | null;
  status: PriceStatus;
  can_delete: boolean;
}

export interface PriceSummary {
  model: string;
  current: PriceRow | null;
  scheduled: PriceRow | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ModelSuggestion {
  model: string;
  last_used_at: string | null;
  has_price: boolean;
}

export interface SuggestionsResponse {
  results: ModelSuggestion[];
}

export interface MissingModel {
  model: string;
  last_used_at: string | null;
  configured: boolean;
}

export interface MissingResponse {
  models: MissingModel[];
  generated_at: string;
}

/** "running" is only ever fresh: the API reports a run stuck for 15+ minutes as "failed". */
export type SyncRunStatus = "never" | "running" | "success" | "failed";

export interface PriceTriple {
  input: string;
  output: string;
  cached: string;
}

export interface SkippedManual {
  model: string;
  ours: PriceTriple;
  litellm: PriceTriple;
}

export interface SyncStatus {
  enabled: boolean;
  last_run_at: string | null;
  last_success_at: string | null;
  last_status: SyncRunStatus;
  last_error: string;
  overdue: boolean;
  next_run_at: string | null;
  summary: {
    added: string[];
    updated: string[];
    unchanged: string[];
    skipped_manual: SkippedManual[];
    skipped_scheduled: string[];
    skipped_concurrent: string[];
    unpriced: string[];
    errored: string[];
  };
}
