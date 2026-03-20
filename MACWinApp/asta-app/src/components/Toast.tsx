import { useEffect, useState } from "react";

export interface ToastData {
  message: string;
  type: "error" | "success" | "info";
}

/** Dispatch this event from anywhere to show a toast. */
export function showToast(message: string, type: ToastData["type"] = "error") {
  window.dispatchEvent(new CustomEvent("asta-toast", { detail: { message, type } }));
}

export default function Toast() {
  const [toast, setToast] = useState<ToastData | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      const { message, type } = (e as CustomEvent<ToastData>).detail;
      setToast({ message, type });
      setVisible(true);
    };
    window.addEventListener("asta-toast", handler);
    return () => window.removeEventListener("asta-toast", handler);
  }, []);

  // Auto-dismiss after 4s
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(() => setVisible(false), 4000);
    return () => clearTimeout(timer);
  }, [visible, toast]);

  if (!visible || !toast) return null;

  const bgColor =
    toast.type === "error"
      ? "rgba(255,59,48,0.18)"
      : toast.type === "success"
        ? "rgba(52,199,89,0.18)"
        : "rgba(255,255,255,0.08)";

  const borderColor =
    toast.type === "error"
      ? "rgba(255,59,48,0.35)"
      : toast.type === "success"
        ? "rgba(52,199,89,0.35)"
        : "rgba(255,255,255,0.12)";

  const textColor =
    toast.type === "error"
      ? "#FF6B6B"
      : toast.type === "success"
        ? "#6BE88B"
        : "var(--label)";

  return (
    <div
      style={{
        position: "fixed",
        top: 12,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 9999,
        maxWidth: 520,
        width: "90%",
        background: bgColor,
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: `1px solid ${borderColor}`,
        borderRadius: 10,
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        animation: "toast-slide-in 0.25s ease-out",
      }}
    >
      <span
        style={{
          flex: 1,
          fontSize: 13,
          color: textColor,
          fontFamily: "inherit",
          lineHeight: 1.4,
          wordBreak: "break-word",
        }}
      >
        {toast.message}
      </span>
      <button
        onClick={() => setVisible(false)}
        style={{
          background: "transparent",
          border: "none",
          color: "var(--label-secondary)",
          cursor: "pointer",
          fontSize: 16,
          padding: "0 2px",
          lineHeight: 1,
          flexShrink: 0,
        }}
        aria-label="Dismiss"
      >
        &times;
      </button>
      <style>{`
        @keyframes toast-slide-in {
          from { opacity: 0; transform: translateX(-50%) translateY(-16px); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
      `}</style>
    </div>
  );
}
