import { Fragment, useId, type ReactNode } from "react";
import { Money } from "../ai-cost/Money";
import { Badge } from "../ai-cost/PageHeader";
import { formatDate, formatDateTime, formatPrice, sourceLabel } from "./format";
import type { PriceSummary } from "./types";

const NOT_YET = "Coming in the next step";

interface Props {
  rows: PriceSummary[];
  expandedModel: string | null;
  onViewHistory: (model: string) => void;
  /** Opens the add-price modal; without it the buttons stay disabled. */
  onAddPrice?: (model?: string) => void;
  renderExpanded?: (model: string) => ReactNode;
}

const TH = "px-4 py-2.5 text-[12px] font-medium text-muted whitespace-nowrap";
const TD_NUM = "px-4 py-3 text-right tabular-nums";
export const PRIMARY_BTN =
  "inline-flex items-center px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-50 disabled:cursor-not-allowed";
const LINK_BTN =
  "rounded-sm text-[13px] font-medium text-ink underline-offset-2 hover:underline disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed";

const price = (v: string) => <Money value={formatPrice(v)} />;

export function AddPriceButton({
  onAddPrice,
  model,
  label,
  ariaLabel,
  className,
}: {
  onAddPrice?: (model?: string) => void;
  model?: string;
  label: string;
  ariaLabel?: string;
  className: string;
}) {
  const reasonId = useId();
  const disabled = !onAddPrice;
  return (
    <>
      <button
        type="button"
        className={`${className}${disabled ? " opacity-50 cursor-not-allowed" : ""}`}
        aria-label={ariaLabel}
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
      <div className="rounded-card border border-line bg-white p-10 text-center">
        <p className="font-medium text-ink">No prices yet</p>
        <p className="mt-1 mb-4 text-[13.5px] text-muted">
          Add a price for at least one model to start tracking AI cost.
        </p>
        <AddPriceButton onAddPrice={onAddPrice} label="Add new price" className={PRIMARY_BTN} />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-line bg-white">
      <table className="w-full min-w-[820px] text-[13.5px]">
        <thead>
          <tr className="border-b border-line bg-[#FBFBFB]">
            <th scope="col" className={`${TH} text-left`}>Model</th>
            <th scope="col" className={`${TH} text-right`}>Input per 1M</th>
            <th scope="col" className={`${TH} text-right`}>Output per 1M</th>
            <th scope="col" className={`${TH} text-right`}>Cached per 1M</th>
            <th scope="col" className={`${TH} text-left`}>Effective from</th>
            <th scope="col" className={`${TH} text-left`}>Source</th>
            <th scope="col" className={TH}>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ model, current, scheduled }) => {
            const expanded = expandedModel === model;
            return (
              <Fragment key={model}>
                <tr className="border-b border-line-soft align-top last:border-0">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-ink">{model}</div>
                    {scheduled && (
                      <div className="mt-1.5 flex flex-col items-start gap-1">
                        <Badge tone="yellow">
                          Scheduled from {formatDateTime(scheduled.effective_from)}
                        </Badge>
                        <span className="text-[12px] text-muted tabular-nums" data-testid="scheduled-prices">
                          {price(scheduled.input_token_price_per_1m)} /{" "}
                          {price(scheduled.output_token_price_per_1m)} /{" "}
                          {price(scheduled.cached_token_price_per_1m)}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className={TD_NUM}>{current ? price(current.input_token_price_per_1m) : "—"}</td>
                  <td className={TD_NUM}>{current ? price(current.output_token_price_per_1m) : "—"}</td>
                  <td className={TD_NUM}>{current ? price(current.cached_token_price_per_1m) : "—"}</td>
                  <td className="px-4 py-3 tabular-nums">{current ? formatDate(current.effective_from) : "—"}</td>
                  <td className="px-4 py-3">{current ? <Badge>{sourceLabel(current.source)}</Badge> : "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
                      <AddPriceButton
                        onAddPrice={onAddPrice}
                        model={model}
                        label="Add price"
                        ariaLabel={`Add price for ${model}`}
                        className={LINK_BTN}
                      />
                      <button
                        type="button"
                        className={LINK_BTN}
                        aria-expanded={expanded}
                        aria-label={`View history for ${model}`}
                        onClick={() => onViewHistory(model)}
                      >
                        History
                      </button>
                    </div>
                  </td>
                </tr>
                {expanded && renderExpanded && (
                  <tr className="border-b border-line-soft bg-[#FBFBFB] last:border-0">
                    <td colSpan={7} className="px-4 py-4 sm:pl-8">
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
