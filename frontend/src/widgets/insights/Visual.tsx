import type { Chapter, InsightVisual } from "./types";

/* Chart tokens for the dark book page (#1B1B1B). Values and labels wear text
   ink; the chapter accent only colours marks. */
const INK = "#FAFAFA";
const INK_2 = "#A1A1AA";
const NEUTRAL = "#52525B";
const SURFACE = "#1B1B1B";
export const ACCENT: Record<Chapter, string> = { attention: "#F87171", good: "#FACC15" };

interface Props {
  visual: InsightVisual;
  tone: Chapter;
  /** Store name, used by the rating line's store label. */
  storeName?: string | null;
}

const fmt1 = (n: number) => n.toFixed(1);
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);

/** A vertical bar with 4px rounded data end and a square baseline. */
function barPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, w / 2, h);
  if (h <= 0) return "";
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/** A horizontal bar with its rounded data end on the right. */
function hbarPath(x: number, y: number, w: number, h: number): string {
  const r = Math.min(4, h / 2, w);
  if (w <= 0) return "";
  return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
}

function Svg({
  label,
  width,
  height,
  children,
}: {
  label: string;
  width: number;
  height: number;
  children: React.ReactNode;
}) {
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      style={{ maxWidth: width, height: "auto", overflow: "visible" }}
      fontFamily="inherit"
    >
      {children}
    </svg>
  );
}

function BeforeNow({ before, now, accent }: { before: number; now: number; accent: string }) {
  const W = 240;
  const H = 180;
  const base = 148;
  const maxH = 104;
  const top = Math.max(before, now, 1);
  const bars = [
    { label: "Before", value: before, x: 40, fill: NEUTRAL },
    { label: "Now", value: now, x: 128, fill: accent },
  ];
  return (
    <Svg label={`Before ${before}, now ${now}`} width={W} height={H}>
      <line x1={20} x2={W - 20} y1={base} y2={base} stroke={NEUTRAL} strokeWidth={1} />
      {bars.map((b) => {
        const h = Math.max(2, (b.value / top) * maxH);
        return (
          <g key={b.label}>
            <path d={barPath(b.x, base - h, 72, h)} fill={b.fill}>
              <title>{`${b.label}: ${b.value}`}</title>
            </path>
            <text x={b.x + 36} y={base - h - 10} textAnchor="middle" fontSize={18} fontWeight={700} fill={INK}>
              {b.value}
            </text>
            <text x={b.x + 36} y={base + 20} textAnchor="middle" fontSize={12} fill={INK_2}>
              {b.label}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

function WaitingDays({ days, accent }: { days: number[]; accent: string }) {
  const list = days.filter(finite).slice(0, 10);
  const W = 260;
  const H = 170;
  const base = 140;
  const maxH = 116;
  const top = Math.max(...list, 1);
  const slot = W / Math.max(list.length, 1);
  const bw = Math.min(26, slot - 6);
  const oldest = list.indexOf(Math.max(...list));
  return (
    <Svg label={`Days waiting for a reply: ${list.join(", ")}`} width={W} height={H}>
      {list.map((d, i) => {
        const h = Math.max(2, (d / top) * maxH);
        const x = i * slot + (slot - bw) / 2;
        return (
          <g key={i}>
            <path d={barPath(x, base - h, bw, h)} fill={accent} opacity={i === oldest ? 1 : 0.55}>
              <title>{`Waiting ${d} ${d === 1 ? "day" : "days"}`}</title>
            </path>
            <text x={x + bw / 2} y={base + 18} textAnchor="middle" fontSize={11.5} fill={i === oldest ? INK : INK_2}>
              {`${d}d`}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

function RatingLine({
  store,
  brand,
  storeName,
  accent,
}: {
  store: number;
  brand: number;
  storeName: string;
  accent: string;
}) {
  const W = 300;
  const H = 136;
  const y = 66;
  const lo = Math.max(1, Math.floor(Math.min(store, brand) - 0.3));
  const hi = 5;
  const sx = (v: number) => 14 + ((v - lo) / (hi - lo)) * (W - 28);
  return (
    <Svg label={`${storeName} ${fmt1(store)} stars, brand ${fmt1(brand)} stars`} width={W} height={H}>
      <line x1={14} x2={W - 14} y1={y} y2={y} stroke={NEUTRAL} strokeWidth={2} strokeLinecap="round" />
      <line x1={sx(brand)} x2={sx(brand)} y1={y - 18} y2={y + 18} stroke={INK} strokeWidth={2} />
      <text x={sx(brand)} y={y - 26} textAnchor="middle" fontSize={12.5} fill={INK}>
        {`Brand ${fmt1(brand)}`}
      </text>
      <circle cx={sx(store)} cy={y} r={9} fill={accent} stroke={SURFACE} strokeWidth={2}>
        <title>{`${storeName}: ${fmt1(store)} stars`}</title>
      </circle>
      <text x={sx(store)} y={y + 36} textAnchor="middle" fontSize={13} fontWeight={600} fill={INK}>
        {`${storeName} ${fmt1(store)}`}
      </text>
      <text x={14} y={H - 4} fontSize={11} fill={INK_2}>{`${lo}★`}</text>
      <text x={W - 14} y={H - 4} textAnchor="end" fontSize={11} fill={INK_2}>{`${hi}★`}</text>
    </Svg>
  );
}

/** Six monthly points, oldest first. */
function ShareLine({ points, accent }: { points: number[]; accent: string }) {
  const pts = points.map((p, i) => ({ i, v: p })).filter((p) => finite(p.v));
  const W = 280;
  const H = 160;
  const top = 30;
  const bottom = 124;
  const vals = pts.map((p) => p.v);
  const min = Math.max(0, Math.min(...vals) - 6);
  const max = Math.min(100, Math.max(...vals) + 6);
  const n = Math.max(points.length - 1, 1);
  const sx = (i: number) => 16 + (i / n) * (W - 40);
  const sy = (v: number) => bottom - ((v - min) / Math.max(max - min, 1)) * (bottom - top);
  const first = pts[0];
  const last = pts[pts.length - 1];
  if (!first || !last) return null;
  return (
    <Svg label={`Share of 5-star reviews by month: ${vals.map((v) => `${Math.round(v)}%`).join(", ")}`} width={W} height={H}>
      <polyline
        points={pts.map((p) => `${sx(p.i)},${sy(p.v)}`).join(" ")}
        fill="none"
        stroke={accent}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {pts.map((p) => (
        <circle key={p.i} cx={sx(p.i)} cy={sy(p.v)} r={p === last ? 6 : 3} fill={accent} stroke={SURFACE} strokeWidth={2}>
          <title>{`${n - p.i === 0 ? "Now" : `${n - p.i} months ago`}: ${Math.round(p.v)}%`}</title>
        </circle>
      ))}
      {first !== last && (
        <text x={sx(first.i)} y={sy(first.v) - 12} textAnchor="start" fontSize={12} fill={INK_2}>
          {`${Math.round(first.v)}%`}
        </text>
      )}
      <text x={sx(last.i)} y={sy(last.v) - 14} textAnchor="middle" fontSize={15} fontWeight={700} fill={INK}>
        {`${Math.round(last.v)}%`}
      </text>
      <text x={sx(0)} y={H - 4} fontSize={11} fill={INK_2}>6 months ago</text>
      <text x={sx(n)} y={H - 4} textAnchor="middle" fontSize={11} fill={INK_2}>Now</text>
    </Svg>
  );
}

function Progress({ before, now, accent }: { before: number; now: number; accent: string }) {
  const W = 260;
  const H = 78;
  const x0 = 4;
  const w = W - 8;
  const pct = (v: number) => Math.max(0, Math.min(100, v));
  const bx = x0 + (pct(before) / 100) * w;
  return (
    <Svg label={`Before ${Math.round(before)}%, now ${Math.round(now)}%`} width={W} height={H}>
      <rect x={x0} y={24} width={w} height={16} rx={8} fill={NEUTRAL} opacity={0.6} />
      <rect x={x0} y={24} width={(pct(now) / 100) * w} height={16} rx={8} fill={accent} />
      <line x1={bx} x2={bx} y1={16} y2={48} stroke={INK} strokeWidth={2} />
      <text x={Math.min(Math.max(bx, 40), W - 120)} y={66} textAnchor="middle" fontSize={12} fill={INK_2}>
        {`Before ${Math.round(before)}%`}
      </text>
      <text x={W - 4} y={70} textAnchor="end" fontSize={18} fontWeight={700} fill={INK}>
        {`${Math.round(now)}%`}
      </text>
    </Svg>
  );
}

/** Average rating per 30-day window, oldest first; bars start at zero. */
function MonthlyBars({ points, accent }: { points: (number | null)[]; accent: string }) {
  const W = 260;
  const H = 176;
  const base = 146;
  const maxH = 112;
  const slot = W / Math.max(points.length, 1);
  const bw = Math.min(30, slot - 8);
  const lastIdx = points.length - 1;
  return (
    <Svg
      label={`Average rating by month: ${points.map((p) => (finite(p) ? fmt1(p) : "no data")).join(", ")}`}
      width={W}
      height={H}
    >
      <line x1={0} x2={W} y1={base} y2={base} stroke={NEUTRAL} strokeWidth={1} />
      {points.map((p, i) => {
        const x = i * slot + (slot - bw) / 2;
        const has = finite(p);
        const h = has ? Math.max(2, (p / 5) * maxH) : 0;
        return (
          <g key={i}>
            {has && (
              <path d={barPath(x, base - h, bw, h)} fill={i === lastIdx ? accent : NEUTRAL}>
                <title>{`${fmt1(p)} stars`}</title>
              </path>
            )}
            <text
              x={x + bw / 2}
              y={base - h - 8}
              textAnchor="middle"
              fontSize={i === lastIdx ? 13 : 11.5}
              fontWeight={i === lastIdx ? 700 : 400}
              fill={i === lastIdx ? INK : INK_2}
            >
              {has ? fmt1(p) : "–"}
            </text>
          </g>
        );
      })}
      <text x={0} y={H - 4} fontSize={11} fill={INK_2}>6 months ago</text>
      <text x={W} y={H - 4} textAnchor="end" fontSize={11} fill={INK_2}>Now</text>
    </Svg>
  );
}

function StoreBars({ items, accent }: { items: { store: string; count: number }[]; accent: string }) {
  const rows = items.slice(0, 6);
  const W = 280;
  const row = 28;
  const H = rows.length * row;
  const nameW = 96;
  const barMax = W - nameW - 36;
  const top = Math.max(...rows.map((r) => r.count), 1);
  const short = (s: string) => (s.length > 14 ? `${s.slice(0, 13)}…` : s);
  return (
    <Svg label={rows.map((r) => `${r.store} ${r.count}`).join(", ")} width={W} height={H}>
      {rows.map((r, i) => {
        const y = i * row + 6;
        const w = Math.max(2, (r.count / top) * barMax);
        return (
          <g key={r.store}>
            <text x={nameW - 8} y={y + 12} textAnchor="end" fontSize={12} fill={INK_2}>
              {short(r.store) !== r.store && <title>{r.store}</title>}
              {short(r.store)}
            </text>
            <path d={hbarPath(nameW, y, w, 16)} fill={accent}>
              <title>{`${r.store}: ${r.count}`}</title>
            </path>
            <text x={nameW + w + 8} y={y + 12.5} fontSize={12.5} fontWeight={600} fill={INK}>
              {r.count}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

export function Visual({ visual, tone, storeName }: Props) {
  const accent = ACCENT[tone];
  switch (visual.kind) {
    case "before_now":
      return <BeforeNow before={visual.before} now={visual.now} accent={accent} />;
    case "waiting_days":
      return <WaitingDays days={visual.days} accent={accent} />;
    case "rating_line":
      return (
        <RatingLine store={visual.store} brand={visual.brand} storeName={storeName || "Store"} accent={accent} />
      );
    case "share_line":
      return <ShareLine points={visual.points} accent={accent} />;
    case "progress":
      return <Progress before={visual.before} now={visual.now} accent={accent} />;
    case "monthly_bars":
      return <MonthlyBars points={visual.points} accent={accent} />;
    case "store_bars":
      return <StoreBars items={visual.items} accent={accent} />;
    default:
      return null;
  }
}
