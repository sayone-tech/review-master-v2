export type Chapter = "attention" | "good";

export type InsightVisual =
  | { kind: "before_now"; before: number; now: number }
  | { kind: "waiting_days"; days: number[] }
  | { kind: "rating_line"; store: number; brand: number }
  | { kind: "share_line"; points: number[] }
  | { kind: "progress"; before: number; now: number }
  | { kind: "monthly_bars"; points: number[] }
  | { kind: "store_bars"; items: { store: string; count: number }[] };

export interface InsightItem {
  type: number;
  chapter: Chapter;
  headline: string;
  title: string;
  body: string;
  visual: InsightVisual;
  link: Record<string, string | number | boolean | null>;
  store: string | null;
  cta: string;
  caption: string;
}

export interface InsightsCover {
  organisation: string;
  reviews: number;
  stores: number;
  attention: number;
  good: number;
}

export interface InsightsBookData {
  cover: InsightsCover | null;
  window: { from: string; to: string } | null;
  items: InsightItem[];
}
