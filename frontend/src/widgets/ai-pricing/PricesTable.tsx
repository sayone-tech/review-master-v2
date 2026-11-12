import { Fragment, useId, type ReactNode } from "react";
import { formatDate, formatDateTime, formatPrice } from "./format";
import type { PriceSummary } from "./types";

const NOT_YET = "Coming in the next step";

interface Props {
  rows: PriceSummary[];
  expandedModel: string | null;
  onViewHistory: (model: string) => void;
  /** Task 8 wires the Add New Price modal here; without it the buttons stay disabled. */
  onAddPrice?: (model?: string) => void;
  renderExpanded?: (model: string) => ReactNode;
}

const TH = "px-4 py-2 text-left font-medium";
const LINK_BTN =
  "text-[13px] font-medium text-ink underline-offset-2 hover:underline disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed";

export function AddPriceButton({
  onAddPrice,
  model,
  label,
  className,
}: {
  onAddPrice?: (model?: string) => void;
  model?: string;
  label: string;
  className: string;
}) {
  const reasonId = useId();
  const disabled = !onAddPrice;
  return (
    <>
      <button
        type="button"
        className={`${className}${disabled ? " opacity-50 cursor-not-allowed" : ""}`}
        aria-disabled={disabled || undefined}
        aria-describedby={disabled ? reasonId : undefined}
        title={disabled ? NOT_YET : undefined}
        onClick={() => onAddPrice?.(model)}
      >
        {label}
      </button>
      {disabled && (
        <span id={reasonId} className="sr-only">
          {NOT_YET}
        </span>
      )}
    </>
  );
}

export function PricesTable({ rows, expandedModel, onViewHistory, onAddPrice, renderExpanded }: Props) {
  if (rows.length === 0) {
    return (
      <div className="bg-white border border-line rounded-card p-8 text-center">
        <p className="text-muted mb-4">
          No pricing configured. Add pricing for at least one model to enable cost tracking.
        </p>
        <AddPriceButton
          onAddPrice={onAddPrice}
          label="Add New Price"
          className="inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>
    );
  }

  return (
    <div className="bg-white border border-line rounded-card overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-line bg-[#FBFBFB] text-[12px] text-muted">
            <th scope="col" className={TH}>Model</th>
            <th scope="col" className={TH}>Input (per 1M tokens)</th>
            <th scope="col" className={TH}>Output (per 1M tokens)</th>
            <th scope="col" className={TH}>Cached Input (per 1M)</th>
            <th scope="col" className={TH}>Effective From</th>
            <th scope="col" className={TH}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ model, current, scheduled }) => {
            const expanded = expandedModel === model;
            return (
              <Fragment key={model}>
                <tr className="border-b border-line align-top">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-ink">{model}</div>
                    {current && (
                      <div className="text-[12px] text-muted">
                        Active since {formatDate(current.effective_from)}
                      </div>
                    )}
                    {scheduled && (
                      <div className="text-[12px] text-amber mt-1">
                        Scheduled: {formatPrice(scheduled.input_token_price_per_1m)}/
                        {formatPrice(scheduled.output_token_price_per_1m)}/
                        {formatPrice(scheduled.cached_token_price_per_1m)} from{" "}
                        {formatDateTime(scheduled.effective_from)}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">{current ? formatPrice(current.input_token_price_per_1m) : "—"}</td>
                  <td className="px-4 py-3">{current ? formatPrice(current.output_token_price_per_1m) : "—"}</td>
                  <td className="px-4 py-3">{current ? formatPrice(current.cached_token_price_per_1m) : "—"}</td>
                  <td className="px-4 py-3">{current ? formatDate(current.effective_from) : "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <AddPriceButton
                        onAddPrice={onAddPrice}
                        model={model}
                        label="Add new price for this model"
                        className={LINK_BTN}
                      />
                      <button
                        type="button"
                        className={LINK_BTN}
                        aria-expanded={expanded}
                        aria-label={`View history for ${model}`}
                        onClick={() => onViewHistory(model)}
                      >
                        View history
                      </button>
                    </div>
                  </td>
                </tr>
                {expanded && renderExpanded && (
                  <tr className="border-b border-line bg-[#FBFBFB]">
                    <td colSpan={6} className="px-4 py-3">
                      {renderExpanded(model)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
