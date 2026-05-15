import type { ActionItemCategory } from "./types";

const CATEGORY_STYLES: Record<ActionItemCategory, { bg: string; text: string; dot: string }> = {
  QUALITY: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-400",
  },
  SERVICE: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    dot: "bg-purple-400",
  },
  EXPERIENCE: {
    bg: "bg-teal-50",
    text: "text-teal-700",
    dot: "bg-teal-400",
  },
  OPERATIONS: {
    bg: "bg-orange-50",
    text: "text-orange-700",
    dot: "bg-orange-400",
  },
  OTHER: {
    bg: "bg-zinc-100",
    text: "text-zinc-500",
    dot: "bg-zinc-400",
  },
};

interface Props {
  category: ActionItemCategory;
  label: string;
}

export function CategoryBadge({ category, label }: Props) {
  const { bg, text, dot } = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.OTHER;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[12px] font-medium ${bg} ${text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}
