"use client";
import { CREATE_ASPECTS, CreateAspect } from "@/lib/createTypes";

interface AspectPickerProps {
  value: CreateAspect;
  onChange: (v: CreateAspect) => void;
  disabled?: boolean;
}

const LABELS: Record<CreateAspect, string> = {
  "9:16": "9:16 · Reels",
  "1:1": "1:1 · Square",
  "16:9": "16:9 · Wide",
};

export function AspectPicker({ value, onChange, disabled }: AspectPickerProps) {
  return (
    <div
      style={{
        background: "var(--color-panel2)",
        border: "1px solid var(--color-line)",
        borderRadius: 11,
        padding: "10px 14px",
      }}
    >
      <p
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: ".7px",
          color: "var(--color-muted2)",
          margin: "0 0 8px",
          fontWeight: 700,
        }}
      >
        3 · Aspect
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {CREATE_ASPECTS.map((a) => {
          const active = a === value;
          return (
            <button
              key={a}
              type="button"
              disabled={disabled}
              onClick={() => onChange(a)}
              style={{
                flex: 1,
                minWidth: 88,
                padding: "8px 10px",
                borderRadius: 8,
                border: `1px solid ${active ? "#3d3470" : "var(--color-line)"}`,
                background: active ? "#1b1430" : "#12121a",
                color: active ? "#ffffff" : "var(--color-muted)",
                fontSize: 12,
                fontWeight: active ? 700 : 600,
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.5 : 1,
              }}
            >
              {LABELS[a]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
