// Phase 25-04 (TDASH-01), restyled as a tug-of-war: complaints pull left (red),
// praise pulls right (yellow). Bars share one scale: the largest count on
// either side of any row is 100% of a half-track.
import { useQuery } from "@tanstack/react-query";
import { Tag } from "lucide-react";

import { fetchTagPolarity } from "./api";
import { FOCUS, Panel, PanelError, PULSE, RED, TIP, YELLOW } from "./Panel";
import type { TagPolarityBar } from "./types";

const ROW = "grid grid-cols-[minmax(0,1fr)_minmax(76px,120px)_minmax(0,1fr)] items-center gap-2";
const SUBTITLE = "All stores, all time";

function pct(count: number, max: number): string {
  return max > 0 ? `${Math.round((count / max) * 1000) / 10}%` : "0%";
}

const POLARITY: Record<TagPolarityBar["polarity_type"], string> = {
  always_positive: "Always positive",
  always_negative: "Always negative",
  mixed: "Mixed",
};

function Side({
  side,
  count,
  max,
  label,
  polarity,
}: {
  side: "complaints" | "praise";
  count: number;
  max: number;
  label: string;
  polarity: TagPolarityBar["polarity_type"];
}) {
  const left = side === "complaints";
  const word = left ? (count === 1 ? "complaint" : "complaints") : "praise";
  return (
    <div className={`flex items-center gap-1.5 ${left ? "flex-row" : "flex-row-reverse"}`}>
      <span
        data-testid={`${side}-count`}
        className={`w-7 shrink-0 text-[12px] tabular-nums text-[#A1A1AA] ${left ? "text-left" : "text-right"}`}
      >
        {count}
      </span>
      <div className={`group relative flex h-[18px] flex-1 items-center ${left ? "justify-end" : "justify-start"}`}>
        <span
          data-testid={`${side}-bar`}
          aria-hidden="true"
          className="block h-2.5 rounded-[5px]"
          style={{ width: pct(count, max), background: left ? RED : YELLOW, minWidth: count > 0 ? 3 : 0 }}
        />
        <span className={`${TIP} bottom-full mb-1 ${left ? "left-0" : "right-0"}`}>
          <strong className="text-[13px] font-semibold text-white tabular-nums">{count}</strong> {word} ·{" "}
          {label}
          <span className="block text-[11px] text-[#71717A]">{POLARITY[polarity]}</span>
        </span>
      </div>
    </div>
  );
}

function TugRow({ tag, max }: { tag: TagPolarityBar; max: number }) {
  return (
    <div
      role="group"
      aria-label={`${tag.label}: ${tag.negative_count} complaints, ${tag.positive_count} praise`}
      className={ROW}
    >
      <Side side="complaints" count={tag.negative_count} max={max} label={tag.label} polarity={tag.polarity_type} />
      <div className="text-center text-[12px] font-medium leading-tight text-white break-words">
        {tag.label}
      </div>
      <Side side="praise" count={tag.positive_count} max={max} label={tag.label} polarity={tag.polarity_type} />
    </div>
  );
}

export function TagPolarityChart() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard", "tag-polarity"],
    queryFn: fetchTagPolarity,
  });

  const tags = data?.tags ?? [];
  const max = Math.max(0, ...tags.flatMap((t) => [t.positive_count, t.negative_count]));

  return (
    <Panel title="Top tags" subtitle={SUBTITLE} busy={isLoading} className="lg:flex-[1.25]">
      {isLoading && (
        <div aria-label="Loading top tags" className="flex flex-col gap-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className={`h-3 rounded ${PULSE}`} />
          ))}
        </div>
      )}

      {isError && (
        <PanelError
          message="Could not load tag distribution."
          onRetry={() => void refetch()}
          retryLabel="Retry loading top tags"
        />
      )}

      {!isLoading && !isError && tags.length === 0 && (
        <p className="py-8 text-center text-[13px] text-[#A1A1AA]">
          No canonical tags yet. Tags will appear as reviews are enriched.
        </p>
      )}

      {!isLoading && !isError && tags.length > 0 && (
        <>
          <div className={`${ROW} mb-2 text-[11px] text-[#71717A]`} aria-hidden="true">
            <span className="text-left">Complaints</span>
            <span />
            <span className="text-right">Praise</span>
          </div>
          <div className="flex flex-col gap-2">
            {tags.map((t) => (
              <TugRow key={t.label} tag={t} max={max} />
            ))}
          </div>

          {data?.has_more && (
            <div className="mt-auto pt-3.5">
              <a
                href="/admin/org/tags/"
                className={`inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[#FACC15] underline underline-offset-2 ${FOCUS}`}
              >
                <Tag size={14} aria-hidden="true" />
                See all tags
              </a>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
