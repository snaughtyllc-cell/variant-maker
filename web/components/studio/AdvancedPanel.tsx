"use client";
import { useState } from "react";

export function AdvancedPanel() {
  const [open, setOpen] = useState(false);

  return (
    <div
      style={{
        marginTop: 16,
        fontSize: 12.5,
        color: "var(--color-muted)",
        borderTop: "1px solid var(--color-line)",
        paddingTop: 14,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ color: "var(--color-muted2)" }}>{open ? "▾" : "▸"}</span>
        Advanced
        <span
          style={{
            marginLeft: "auto",
            color: "var(--color-text)",
            background: "#14141d",
            border: "1px solid var(--color-line)",
            padding: "4px 10px",
            borderRadius: 999,
            fontSize: 11.5,
          }}
        >
          Output: Vertical 1080×1920 ▾
        </span>
      </div>
      {open && (
        <div
          style={{
            marginTop: 10,
            padding: "10px 12px",
            background: "var(--color-panel2)",
            borderRadius: 8,
            border: "1px solid var(--color-line)",
            fontSize: 12,
            color: "var(--color-muted)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Output format</span>
            <span style={{ color: "var(--color-text)", fontWeight: 600 }}>Vertical 1080×1920</span>
          </div>
        </div>
      )}
    </div>
  );
}
