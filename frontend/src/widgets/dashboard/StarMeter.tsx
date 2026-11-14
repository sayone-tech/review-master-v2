const STAR_PATH =
  "M12 1.5l3.1 6.5 7.1.9-5.2 4.9 1.3 7.1L12 17.4l-6.3 3.5 1.3-7.1L1.8 8.9l7.1-.9z";

interface Props {
  value: number;
  /** Edge length of one star in px. */
  size?: number;
}

function Stars({ size, color }: { size: number; color: string }) {
  return (
    // Equal cells, no gap: a clip at value/5 of the row is exact per star.
    <span className="flex shrink-0">
      {Array.from({ length: 5 }, (_, i) => (
        <svg key={i} width={size * 1.2} height={size} viewBox="-2 0 28 24" aria-hidden="true" className="shrink-0">
          <path d={STAR_PATH} fill={color} />
        </svg>
      ))}
    </span>
  );
}

/** Five stars clip-filled to exactly value/5 (yellow over dim grey). */
export function StarMeter({ value, size = 22 }: Props) {
  const v = Number.isFinite(value) ? Math.min(5, Math.max(0, value)) : 0;
  const pct = Math.round((v / 5) * 100);
  return (
    <span
      role="img"
      aria-label={`Average rating ${v.toFixed(1)} out of 5`}
      className="relative inline-flex"
    >
      <Stars size={size} color="#2A2A2A" />
      <span
        data-testid="star-meter-fill"
        className="absolute inset-y-0 left-0 overflow-hidden"
        style={{ width: `${pct}%` }}
      >
        <Stars size={size} color="#FACC15" />
      </span>
    </span>
  );
}
