interface Props {
  points: (number | null)[];
  /** Names the series for screen readers, e.g. "Reviews per period". */
  label?: string;
  color?: string;
}

const W = 140;
const H = 26;
const PAD = 4; // keeps the 2px stroke and end dot inside the box

/**
 * Small trend line. Null points leave a gap; renders nothing with fewer than
 * two real points. Stroke stays 2px however wide the box is stretched.
 */
export function Sparkline({ points, label = "Trend", color = "#FACC15" }: Props) {
  const real = points.filter((p): p is number => p !== null && Number.isFinite(p));
  if (real.length < 2) return null;

  const min = Math.min(...real);
  const max = Math.max(...real);
  const step = points.length > 1 ? W / (points.length - 1) : 0;
  const y = (v: number) =>
    max === min ? H / 2 : PAD + (1 - (v - min) / (max - min)) * (H - PAD * 2);

  // Split into runs of consecutive non-null points.
  const runs: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (p === null || !Number.isFinite(p)) {
      if (run.length) runs.push(run);
      run = [];
    } else {
      run.push({ x: i * step, y: y(p) });
    }
  });
  if (run.length) runs.push(run);

  const last = runs[runs.length - 1][runs[runs.length - 1].length - 1];
  const described = points.map((p) => (p === null ? "no data" : String(p))).join(", ");

  // A zero-length line with round caps draws a dot that, unlike a circle,
  // stays round under preserveAspectRatio="none".
  const dot = (pt: { x: number; y: number }, key: string, width: number) => (
    <line
      key={key}
      x1={pt.x}
      y1={pt.y}
      x2={pt.x}
      y2={pt.y}
      stroke={color}
      strokeWidth={width}
      strokeLinecap="round"
      vectorEffect="non-scaling-stroke"
    />
  );

  return (
    <svg
      role="img"
      aria-label={`${label}: ${described}`}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="block w-full overflow-visible"
      style={{ maxWidth: W, height: H }}
    >
      {runs.map((r, i) =>
        r.length === 1 ? (
          dot(r[0], `iso-${i}`, 4)
        ) : (
          <polyline
            key={`run-${i}`}
            points={r.map((pt) => `${pt.x},${pt.y}`).join(" ")}
            fill="none"
            stroke={color}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        ),
      )}
      {dot(last, "end", 6)}
    </svg>
  );
}
