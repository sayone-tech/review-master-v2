import type { ActionItemScope } from "./types";

const SCOPE_STYLE: Record<
  ActionItemScope,
  { bg: string; text: string; label: string }
> = {
  SHOP: { bg: "bg-line-soft", text: "text-muted", label: "Shop" },
  BRAND: { bg: "bg-amber-tint", text: "text-amber", label: "Brand" },
};

interface Props {
  scope: ActionItemScope;
}

export function ScopePill({ scope }: Props) {
  const style = SCOPE_STYLE[scope];
  return (
    <span
      className={`inline-flex items-center text-[12px] font-semibold rounded-full px-2 py-1 ${style.bg} ${style.text}`}
    >
      {style.label}
    </span>
  );
}
