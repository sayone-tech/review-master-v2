import { useId, useRef, useState } from "react";
import { Modal } from "../modal";
import { ApiError, createPrice } from "./api";
import { ModelAutocomplete } from "./ModelAutocomplete";

interface Props {
  open: boolean;
  initialModel: string;
  onClose: () => void;
  onSaved: () => void;
}

type FieldKey =
  | "model"
  | "input_token_price_per_1m"
  | "output_token_price_per_1m"
  | "cached_token_price_per_1m"
  | "effective_from";
type Errors = Partial<Record<FieldKey, string>>;

const PAST_GRACE_MS = 5000; // mirrors the server's backdating grace
const PRICE_RE = /^(\d+\.?\d*|\.\d+)$/;
const RANGE_MSG = "Must be a number from 0 to 1000.";

const PRICE_FIELDS: { key: FieldKey; label: string }[] = [
  { key: "input_token_price_per_1m", label: "Input price (USD per 1M tokens)" },
  { key: "output_token_price_per_1m", label: "Output price (USD per 1M tokens)" },
  { key: "cached_token_price_per_1m", label: "Cached input price (USD per 1M tokens)" },
];

const pad = (n: number) => String(n).padStart(2, "0");

/** Local `YYYY-MM-DDTHH:mm` for the next whole minute, so the default is never "in the past". */
function defaultFrom(): string {
  const d = new Date(Math.ceil(Date.now() / 60000) * 60000);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function validatePrice(raw: string): string | null {
  const v = raw.trim();
  if (!v) return "Enter a price.";
  if (!PRICE_RE.test(v)) return RANGE_MSG;
  if ((v.split(".")[1] ?? "").length > 8) return "No more than 8 decimal places.";
  if (Number(v) > 1000) return RANGE_MSG;
  return null;
}

function utcFrom(local: string): Date | null {
  if (!local) return null;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d;
}

const INPUT = "w-full px-3 py-2 border border-line rounded-md text-[13.5px] bg-white";

export function AddPriceModal({ open, initialModel, onClose, onSaved }: Props) {
  // Remounted by the parent per open, so state initialises fresh each time.
  const [model, setModel] = useState(initialModel);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [from, setFrom] = useState(defaultFrom);
  const [errors, setErrors] = useState<Errors>({});
  const [topError, setTopError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const uid = useId();
  const formId = `${uid}-form`;
  const inFlight = useRef(false);

  const fromDate = utcFrom(from);
  const utcLine = fromDate
    ? `This price will apply from ${fromDate.toISOString().slice(0, 19).replace("T", " ")} UTC.`
    : null;

  const validate = (): Errors => {
    const e: Errors = {};
    const m = model.trim();
    if (!m) e.model = "Model is required.";
    else if (m.length > 100) e.model = "Model must be 100 characters or fewer.";
    for (const { key } of PRICE_FIELDS) {
      const msg = validatePrice(prices[key] ?? "");
      if (msg) e[key] = msg;
    }
    if (!fromDate) e.effective_from = "Choose a date and time.";
    else if (fromDate.getTime() < Date.now() - PAST_GRACE_MS)
      e.effective_from = "Effective from can't be in the past.";
    return e;
  };

  const submit = async () => {
    if (inFlight.current) return;
    const e = validate();
    setErrors(e);
    setTopError(null);
    if (Object.keys(e).length > 0 || !fromDate) return;
    inFlight.current = true;
    setSaving(true);
    try {
      await createPrice({
        model: model.trim(),
        input_token_price_per_1m: prices.input_token_price_per_1m.trim(),
        output_token_price_per_1m: prices.output_token_price_per_1m.trim(),
        cached_token_price_per_1m: prices.cached_token_price_per_1m.trim(),
        effective_from: fromDate.toISOString(),
      });
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.fields) {
        const next: Errors = {};
        const stray: string[] = [];
        for (const [k, msgs] of Object.entries(err.fields)) {
          if (k === "model" || k === "effective_from" || PRICE_FIELDS.some((f) => f.key === k))
            next[k as FieldKey] = msgs.join(" ");
          else stray.push(msgs.join(" "));
        }
        setErrors(next);
        if (stray.length) setTopError(stray.join(" "));
      } else {
        setTopError(err instanceof Error ? err.message : "Could not save the price.");
      }
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  };

  const errId = (k: FieldKey) => `${uid}-${k}-err`;
  const fieldErr = (k: FieldKey) =>
    errors[k] ? (
      <p id={errId(k)} className="mt-1 text-[12.5px] text-red">
        {errors[k]}
      </p>
    ) : null;
  const aria = (k: FieldKey) => ({
    "aria-invalid": errors[k] ? true : undefined,
    "aria-describedby": errors[k] ? errId(k) : undefined,
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add New Price"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 bg-white border border-line rounded-md text-[13.5px] hover:bg-line-soft"
          >
            Cancel
          </button>
          <button
            type="submit"
            form={formId}
            disabled={saving}
            className="px-3.5 py-2 bg-yellow text-black border border-yellow-hover rounded-md text-[13.5px] font-medium hover:bg-yellow-hover disabled:opacity-50"
          >
            Save
          </button>
        </>
      }
    >
      <form
        id={formId}
        className="space-y-4"
        noValidate
        // The Save button lives in the modal footer (outside the form's subtree); handle Enter
        // explicitly so it submits regardless of the browser's implicit-submission rules.
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.target instanceof HTMLInputElement && !e.defaultPrevented) {
            e.preventDefault();
            void submit();
          }
        }}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {topError && (
          <div role="alert" className="text-[13px] text-red bg-red-50 border border-red-200 rounded-md p-3">
            {topError}
          </div>
        )}
        <div>
          <label htmlFor={`${uid}-model`} className="block text-[13px] font-medium mb-1">
            Model
          </label>
          <ModelAutocomplete id={`${uid}-model`} value={model} onChange={setModel} {...aria("model")} />
          {fieldErr("model")}
        </div>
        {PRICE_FIELDS.map(({ key, label }) => (
          <div key={key}>
            <label htmlFor={`${uid}-${key}`} className="block text-[13px] font-medium mb-1">
              {label}
            </label>
            <input
              id={`${uid}-${key}`}
              type="text"
              inputMode="decimal"
              className={INPUT}
              value={prices[key] ?? ""}
              onChange={(e) => setPrices((p) => ({ ...p, [key]: e.target.value }))}
              {...aria(key)}
            />
            {fieldErr(key)}
          </div>
        ))}
        <div>
          <label htmlFor={`${uid}-from`} className="block text-[13px] font-medium mb-1">
            Effective from
          </label>
          <input
            id={`${uid}-from`}
            type="datetime-local"
            className={INPUT}
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            {...aria("effective_from")}
          />
          {fieldErr("effective_from")}
          {utcLine && <p className="mt-1 text-[12.5px] text-muted">{utcLine}</p>}
        </div>
      </form>
    </Modal>
  );
}
