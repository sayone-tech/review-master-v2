import type { ActionItemStatus } from "./types";
import { STATUS_LABEL } from "./types";

const STATUS_STYLE: Record<
  ActionItemStatus,
  { bg: string; text: string }
> = {
  TODO: { bg: "bg-line-soft", text: "text-muted" },
  IN_PROGRESS: { bg: "bg-blue-tint", text: "text-blue" },
  COMPLETE: { bg: "bg-green-tint", text: "text-green" },
  WONT_DO: { bg: "bg-red-tint", text: "text-red" },
};

interface Props {
  status: ActionItemStatus;
}

export function StatusBadge({ status }: Props) {
  const style = STATUS_STYLE[status];
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap text-[12px] font-semibold rounded-full px-2 py-1 ${style.bg} ${style.text}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
