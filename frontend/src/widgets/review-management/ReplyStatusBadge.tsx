import { CheckCircle } from "lucide-react";

interface Props {
  isReplied: boolean;
}

const REPLIED = { backgroundColor: "#DCFCE7", color: "#16A34A" } as const;
const PENDING = { backgroundColor: "#FEF3C7", color: "#D97706" } as const;

export function ReplyStatusBadge({ isReplied }: Props) {
  if (isReplied) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 text-[12px] font-semibold rounded-full"
        style={REPLIED}
      >
        <CheckCircle size={12} aria-hidden="true" />
        Replied
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 text-[12px] font-semibold rounded-full"
      style={PENDING}
    >
      Not Replied
    </span>
  );
}
