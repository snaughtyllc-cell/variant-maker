"use client";

import { IdentityMode } from "@/lib/createTypes";

const LABELS: Record<IdentityMode, string> = {
  face: "Face refs",
  lora: "LoRAs",
  both: "Both",
};

interface IdentityModeTabsProps {
  value: IdentityMode;
  onChange: (mode: IdentityMode) => void;
  disabled?: boolean;
}

export function IdentityModeTabs({
  value,
  onChange,
  disabled,
}: IdentityModeTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Identity mode"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: 6,
        marginBottom: 12,
      }}
    >
      {(Object.keys(LABELS) as IdentityMode[]).map((mode) => {
        const active = value === mode;
        return (
          <button
            key={mode}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            onClick={() => onChange(mode)}
            style={{
              border: active
                ? "1px solid var(--color-violet)"
                : "1px solid var(--color-line)",
              background: active ? "#1a1430" : "var(--color-panel2)",
              color: active ? "var(--color-violet-l)" : "var(--color-muted)",
              borderRadius: 9,
              padding: "8px 6px",
              fontSize: 12,
              fontWeight: 700,
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.55 : 1,
            }}
          >
            {LABELS[mode]}
          </button>
        );
      })}
    </div>
  );
}
