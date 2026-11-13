import { Search } from "lucide-react";

export interface FilterSearchProps {
  value: string;
  placeholder: string;
  ariaLabel: string;
  onChange: (v: string) => void;
  onSubmit?: () => void;
}

export function FilterSearch({ value, placeholder, ariaLabel, onChange, onSubmit }: FilterSearchProps) {
  return (
    <div className="relative flex-1 min-w-[160px] inline-flex items-center">
      <Search size={15} strokeWidth={1.8} className="absolute left-[11px] text-muted pointer-events-none" />
      <input
        type="search"
        aria-label={ariaLabel}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSubmit?.();
        }}
        className="w-full h-[34px] pl-[32px] pr-3 text-[13px] text-text placeholder:text-faint bg-white border border-line rounded-[8px] outline-none transition-[border-color,box-shadow] focus:border-ink focus-visible:shadow-[0_0_0_3px_rgba(10,10,10,0.1)]"
      />
    </div>
  );
}
