export type ToastKind = "success" | "error" | "info" | "warning";

export interface ToastDetail {
  kind: ToastKind;
  title: string;
  msg?: string;
}

/**
 * Dispatch an `app:toast` CustomEvent on window.
 * Picked up by the Alpine.js listener in templates/components/toasts.html.
 */
export function emitToast(detail: ToastDetail): void {
  window.dispatchEvent(new CustomEvent("app:toast", { detail }));
}
