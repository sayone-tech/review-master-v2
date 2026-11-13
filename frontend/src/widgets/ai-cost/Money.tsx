/**
 * Splits a formatted amount ("$1,245.67000000") into its significant part and the trailing
 * zeros after it. Cents always stay significant, so "$3.00000000" splits as "$3.00" + "000000".
 */
export function splitMoney(text: string): [string, string] {
  const m = /^(.*\.\d\d\d*?)(0*)$/.exec(text);
  return m ? [m[1], m[2]] : [text, ""];
}

/** A cost or price with full precision, the padding zeros faded so the real digits read first. */
export function Money({ value, className = "" }: { value: string; className?: string }) {
  const [sig, zeros] = splitMoney(value);
  return (
    <span className={`whitespace-nowrap tabular-nums ${className}`}>
      {sig}
      {zeros && <span className="text-subtle">{zeros}</span>}
    </span>
  );
}

/** Thin bar under a cost showing its share of the period total. */
export function ShareBar({ cost, total }: { cost: string; total: number }) {
  if (!(total > 0)) return null;
  const pct = Math.min(100, Math.max(0, (Number(cost) / total) * 100));
  return (
    <span
      aria-hidden="true"
      title={`${pct < 1 && pct > 0 ? "<1" : Math.round(pct)}% of total`}
      className="mt-1.5 ml-auto block h-1 w-16 overflow-hidden rounded-full bg-line-soft"
      data-testid="share-bar"
    >
      <span className="block h-full rounded-full bg-yellow" style={{ width: `${pct}%` }} />
    </span>
  );
}
