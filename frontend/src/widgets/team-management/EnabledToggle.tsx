interface EnabledToggleProps {
  enabled: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onDisableRequest?: () => void;
  onEnableRequest?: () => void;
  memberName: string;
}

export function EnabledToggle({
  enabled,
  disabled,
  disabledReason,
  onDisableRequest,
  onEnableRequest,
  memberName,
}: EnabledToggleProps) {
  const handleClick = () => {
    if (disabled) return;
    if (enabled) onDisableRequest?.();
    else onEnableRequest?.();
  };
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={`${memberName} enabled`}
      aria-disabled={disabled || undefined}
      title={disabled ? (disabledReason ?? "") : undefined}
      onClick={handleClick}
      className={`inline-flex items-center gap-2 ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`relative w-10 h-6 rounded-full transition-colors duration-150 flex-shrink-0 overflow-hidden ${
          enabled ? "bg-green" : "bg-line"
        }`}
      >
        <span
          aria-hidden="true"
          className={`absolute top-1 ${enabled ? "left-5" : "left-1"} w-4 h-4 bg-white rounded-full transition-[left] duration-150`}
        />
      </span>
      <span className={`text-[13px] font-medium ${enabled ? "text-green" : "text-muted"}`}>
        {enabled ? "Enabled" : "Disabled"}
      </span>
    </button>
  );
}
