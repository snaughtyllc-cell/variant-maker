"use client";
import { useState } from "react";

interface AdvancedPanelProps {
  allowCreativeEscalate: boolean;
  onAllowCreativeEscalateChange: (value: boolean) => void;
  qualityMode: "fast" | "hq";
  onQualityModeChange: (value: "fast" | "hq") => void;
}

export function AdvancedPanel({
  allowCreativeEscalate,
  onAllowCreativeEscalateChange,
  qualityMode,
  onQualityModeChange,
}: AdvancedPanelProps) {
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

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginTop: 12 }}>
            <span>
              Quality
              <span
                style={{
                  display: "block",
                  fontSize: 10.5,
                  color: "var(--color-muted2)",
                  marginTop: 2,
                  lineHeight: 1.4,
                }}
              >
                Fast is quick, non-AI. HQ runs AI upscale — sharper and more
                different. First HQ variant often sits on rendering for several
                minutes with no thumb.
              </span>
            </span>
            <select
              value={qualityMode}
              onChange={(e) => onQualityModeChange(e.target.value === "hq" ? "hq" : "fast")}
              style={{
                marginLeft: 12,
                flexShrink: 0,
                background: "#16161f",
                color: "var(--color-text)",
                border: "1px solid var(--color-line)",
                borderRadius: 8,
                padding: "6px 8px",
                fontSize: 12,
              }}
            >
              <option value="fast">Fast</option>
              <option value="hq">HQ (Phase 8)</option>
            </select>
          </div>

          <label
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 12,
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <span>
              Allow creative escalate
              <span
                style={{
                  display: "block",
                  fontSize: 10.5,
                  color: "var(--color-muted2)",
                  marginTop: 2,
                  lineHeight: 1.4,
                }}
              >
                Optimized for uniqueness while keeping a clean look — spends one
                stronger-preset attempt if lighter passes don&apos;t clear the target.
              </span>
            </span>
            <input
              type="checkbox"
              checked={allowCreativeEscalate}
              onChange={(e) => onAllowCreativeEscalateChange(e.target.checked)}
              style={{ width: 16, height: 16, flexShrink: 0, marginLeft: 12, accentColor: "#7c5cff" }}
            />
          </label>
        </div>
      )}
    </div>
  );
}
