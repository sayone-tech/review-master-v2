import type { ReactNode } from "react";

/** Page title row: title (+ optional badge) and subtitle on the left, controls on the right. */
export function PageHeader({
  title,
  badge,
  sub,
  children,
}: {
  title: ReactNode;
  badge?: ReactNode;
  sub?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
            {title}
          </h1>
          {badge}
        </div>
        {sub && <p className="mt-1 text-[14px] text-muted">{sub}</p>}
      </div>
      {children}
    </header>
  );
}

export type BadgeTone = "neutral" | "gray" | "green" | "amber" | "blue" | "yellow";

const BADGE_TONES: Record<BadgeTone, [string, string]> = {
  neutral: ["bg-line-soft text-muted", "bg-faint"],
  gray: ["bg-line-soft text-subtle", "bg-faint"],
  green: ["bg-green-tint text-[#166534]", "bg-green"],
  amber: ["bg-amber-tint text-[#92400E]", "bg-amber"],
  blue: ["bg-blue-tint text-[#1E40AF]", "bg-blue"],
  yellow: ["bg-yellow-tint text-[#854D0E]", "bg-yellow"],
};

/** The design system's pill badge (`.badge`), optionally with a status dot. */
export function Badge({
  tone = "neutral",
  dot = false,
  children,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
}) {
  const [cls, dotCls] = BADGE_TONES[tone];
  return (
    <span
      className={`inline-flex items-center gap-[5px] whitespace-nowrap rounded-full px-2 py-0.5 text-[12px] font-medium ${cls}`}
    >
      {dot && <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${dotCls}`} />}
      {children}
    </span>
  );
}

/** Neutral pill used for organisation type and shop region. */
export function NeutralBadge({ children }: { children: ReactNode }) {
  return <Badge>{children}</Badge>;
}

/** White card with a title row; the body (usually a table) scrolls horizontally on small screens. */
export function TableCard({
  title,
  meta,
  children,
  className = "",
}: {
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`overflow-hidden rounded-card border border-line bg-white ${className}`}>
      <div className="flex items-baseline justify-between gap-3 px-4 py-3">
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {meta && <span className="text-[12px] text-muted">{meta}</span>}
      </div>
      {children}
    </section>
  );
}
