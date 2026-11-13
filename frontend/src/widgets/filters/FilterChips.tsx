import { X } from "lucide-react";

export interface FilterChip {
  key: string;
  label: string;
  onRemove: () => void;
}

export interface FilterChipsProps {
  chips: FilterChip[];
  onClearAll: () => void;
}

export function FilterChips({ chips, onClearAll }: FilterChipsProps) {
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-[6px] mt-[9px]">
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-[6px] text-[12px] bg-yellow-tint border border-[#FDE68A] text-[#713F12] rounded-full py-[3px] pl-[10px] pr-[6px]"
        >
          {chip.label}
          <button
            type="button"
            aria-label={`Remove filter: ${chip.label}`}
            onClick={chip.onRemove}
            className="inline-flex items-center justify-center rounded-full cursor-pointer hover:bg-[#FDE68A] focus-visible:outline-2 focus-visible:outline-ink"
          >
            <X size={12} />
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={onClearAll}
        className="text-[12px] text-muted underline cursor-pointer focus-visible:outline-2 focus-visible:outline-ink rounded-sm"
      >
        Clear all
      </button>
    </div>
  );
}
