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
      className={`relative w-10 h-6 rounded-full transition-colors duration-150 ${
        enabled ? "bg-green" : "bg-line"
      } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        aria-hidden="true"
        className={`absolute top-1 ${enabled ? "left-5" : "left-1"} w-4 h-4 bg-white rounded-full transition-[left] duration-150`}
      />
    </button>
  );
}
