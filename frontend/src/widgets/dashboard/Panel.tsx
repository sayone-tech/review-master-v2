import type { ReactNode } from "react";

// Shared shell for the dark dashboard panels: #141414 on the #0A0A0A band.
export const PANEL =
  "bg-[#141414] border border-[#232323] text-[#E4E4E7] rounded-[14px] p-4 sm:p-[18px] flex flex-col min-w-0";
export const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FACC15]";
export const PULSE = "bg-[#1C1C1C] motion-safe:animate-[sk-pulse_1.6s_ease-in-out_infinite]";
export const YELLOW = "#FACC15";
export const GREY = "#52525B";
export const RED = "#F87171";
/**
 * Tooltip box; parent must be `group relative`. Hidden with display:none (not
 * visibility) so an unshown tooltip takes no layout space and never widens the
 * page on phones. Anchor it so it opens towards the panel's centre.
 */
export const TIP =
  "pointer-events-none hidden absolute z-20 w-max max-w-[220px] rounded-lg border border-[#333] bg-[#1C1C1C] px-2.5 py-1.5 text-[12px] leading-snug text-[#A1A1AA] shadow-lg group-hover:block group-focus-visible:block";

interface PanelProps {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  className?: string;
  busy?: boolean;
  label?: string;
}

export function Panel({ title, subtitle, children, className = "", busy, label }: PanelProps) {
  return (
    <section
      aria-label={label ?? title}
      aria-busy={busy || undefined}
      className={`${PANEL} ${className}`}
    >
      <h2 className="text-[14px] font-semibold text-white mb-0.5">{title}</h2>
      {subtitle && <p className="text-[12px] text-[#71717A] mb-3.5 leading-snug">{subtitle}</p>}
      {!subtitle && <div className="mb-3" />}
      {children}
    </section>
  );
}

export function PanelError({
  message = "Could not load.",
  onRetry,
  retryLabel,
}: {
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 py-4 text-[13px] text-[#A1A1AA]">
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          aria-label={retryLabel}
          className={`font-semibold text-[#FACC15] underline underline-offset-2 ${FOCUS}`}
        >
          Retry
        </button>
      )}
    </div>
  );
}
