import { useEffect, useState } from "react";

interface ErrorBannerProps {
  message: string | null;
  onDismiss: () => void;
  autoHide?: boolean;
  autoHideDelay?: number;
}

export function ErrorBanner({
  message,
  onDismiss,
  autoHide = true,
  autoHideDelay = 5000,
}: ErrorBannerProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (message) {
      setVisible(true);

      if (autoHide) {
        const timer = setTimeout(() => {
          setVisible(false);
          setTimeout(onDismiss, 300); // Wait for fade-out animation
        }, autoHideDelay);

        return () => clearTimeout(timer);
      }
    } else {
      setVisible(false);
    }
  }, [message, autoHide, autoHideDelay, onDismiss]);

  if (!message) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 20,
        right: 20,
        maxWidth: 500,
        backgroundColor: "#7f1d1d",
        color: "#fff",
        padding: "16px 20px",
        borderRadius: 12,
        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(-10px)",
        transition: "all 0.3s ease",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      <div style={{ flex: 1 }}>
        <strong style={{ display: "block", marginBottom: 4 }}>Error</strong>
        <div style={{ fontSize: 14, opacity: 0.9 }}>{message}</div>
      </div>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(onDismiss, 300);
        }}
        style={{
          background: "rgba(255, 255, 255, 0.2)",
          border: "none",
          color: "#fff",
          cursor: "pointer",
          padding: "4px 8px",
          borderRadius: 6,
          fontSize: 18,
          lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  );
}
