import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { ChevronDown, Search } from "lucide-react";

/**
 * Black filter card used on the Shops and Team pages (owner-approved sample B):
 * search + dark select pills on the left, a yellow "add" end-cap on the right
 * (along the bottom on phones).
 */
export function NightFilterCard({ children, action }: { children: ReactNode; action: ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row bg-[#0A0A0A] rounded-[16px] overflow-hidden">
      <div className="flex-1 min-w-0 p-3 flex flex-wrap items-center gap-2">{children}</div>
      {action}
    </div>
  );
}

export function NightSearch(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-[1_1_220px] min-w-0 items-center gap-2 bg-[#141414] border border-[#262626] rounded-[11px] px-3 py-2 focus-within:border-yellow">
      <Search size={15} className="shrink-0 text-[#A1A1AA]" aria-hidden="true" />
      <input
        type="search"
        {...props}
        className="w-full min-w-0 bg-transparent text-[14px] text-white placeholder:text-[#A1A1AA] focus:outline-none"
      />
    </label>
  );
}

interface NightSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  "data-testid"?: string;
}

export function NightSelect({ label, children, disabled, ...rest }: NightSelectProps) {
  return (
    <label
      className={`relative flex flex-1 sm:flex-none items-center gap-2 bg-[#141414] border border-[#262626] rounded-[11px] pl-3 pr-8 py-2 text-[13px] text-white focus-within:border-yellow${disabled ? " opacity-50" : ""}`}
    >
      <span className="text-[12px] text-[#A1A1AA] whitespace-nowrap">{label}</span>
      <select
        {...rest}
        disabled={disabled}
        className="min-w-0 appearance-none bg-transparent text-white focus:outline-none disabled:cursor-not-allowed [&_option]:text-black"
      >
        {children}
      </select>
      <ChevronDown
        size={13}
        className="pointer-events-none absolute right-3 text-[#A1A1AA]"
        aria-hidden="true"
      />
    </label>
  );
}

interface NightAddButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  detail: string;
  blocked?: boolean;
}

export function NightAddButton({ label, detail, blocked = false, ...rest }: NightAddButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      {...(blocked ? { "aria-disabled": true } : {})}
      className={`flex flex-row-reverse sm:flex-row items-center justify-between sm:justify-start gap-3.5 px-[18px] py-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-black ${
        blocked
          ? "bg-[#262626] text-[#A1A1AA] cursor-not-allowed"
          : "bg-yellow text-black hover:bg-yellow-hover"
      }`}
    >
      <span className="text-[26px] font-extrabold leading-none" aria-hidden="true">
        +
      </span>
      <span className="text-[12px] leading-snug">
        <b className="block text-[14px] font-bold whitespace-nowrap">{label}</b>
        {detail}
      </span>
    </button>
  );
}
