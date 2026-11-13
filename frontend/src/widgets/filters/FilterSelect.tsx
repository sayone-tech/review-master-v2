import type { LucideIcon } from "lucide-react";
import { ChevronDown } from "lucide-react";

export interface FilterSelectProps<T extends string | number> {
  icon: LucideIcon;
  ariaLabel: string;
  placeholder: string;
  value: T | undefined;
  options: { value: T; label: string }[];
  onChange: (v: T | undefined) => void;
}

export function FilterSelect<T extends string | number>({
  icon: Icon,
  ariaLabel,
  placeholder,
  value,
  options,
  onChange,
}: FilterSelectProps<T>) {
  return (
    <div className="relative inline-flex items-center">
      <Icon size={15} strokeWidth={1.8} className="absolute left-[11px] text-muted pointer-events-none" />
      <select
        aria-label={ariaLabel}
        value={value === undefined ? "" : String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") return onChange(undefined);
          onChange(options.find((o) => String(o.value) === raw)?.value);
        }}
        className="appearance-none h-[34px] pl-[32px] pr-8 text-[13px] text-text bg-white border border-line rounded-[8px] outline-none cursor-pointer transition-[border-color,box-shadow] focus:border-ink focus-visible:shadow-[0_0_0_3px_rgba(10,10,10,0.1)]"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown size={13} className="absolute right-[10px] text-faint pointer-events-none" />
    </div>
  );
}
