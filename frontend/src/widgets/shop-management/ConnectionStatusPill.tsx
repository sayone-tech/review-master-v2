import type { CSSProperties } from "react";
import type { ConnectionMethod, ConnectionStatus } from "./types";

interface PillSpec {
  dotColor: string;
  label: string;
  bgColor: string;
  textColor: string;
}

function pillFor(method: ConnectionMethod, status: ConnectionStatus): PillSpec {
  if (status === "ERROR" || status === "EXPIRED") {
    return { dotColor: "#DC2626", label: "Connection error", bgColor: "#FEF2F2", textColor: "#DC2626" };
  }
  if (status === "QUOTA_EXCEEDED") {
    return { dotColor: "#D97706", label: "Quota exceeded", bgColor: "#FFFBEB", textColor: "#D97706" };
  }
  if (method === "GOOGLE_OAUTH" && status === "CONNECTED") {
    return { dotColor: "#16A34A", label: "Connected via Google", bgColor: "#F0FDF4", textColor: "#16A34A" };
  }
  if (method === "MANUAL" && status === "CONNECTED") {
    return { dotColor: "#2563EB", label: "Connected via API key", bgColor: "#EFF6FF", textColor: "#2563EB" };
  }
  // NOT_CONNECTED or any fallback
  return { dotColor: "#6B7280", label: "Not connected", bgColor: "#F9FAFB", textColor: "#6B7280" };
}

export function ConnectionStatusPill({
  method,
  status,
}: {
  method: ConnectionMethod;
  status: ConnectionStatus;
}) {
  const p = pillFor(method, status);
  const containerStyle: CSSProperties = { backgroundColor: p.bgColor, color: p.textColor };
  const dotStyle: CSSProperties = { backgroundColor: p.dotColor };
  return (
    <span
      data-testid="connection-status-pill"
      style={containerStyle}
      className="inline-flex items-center gap-1.5 px-2 py-[3px] rounded-full text-[12px] font-medium"
    >
      <span
        style={dotStyle}
        className="w-1.5 h-1.5 rounded-full shrink-0"
        aria-hidden="true"
      />
      {p.label}
    </span>
  );
}
