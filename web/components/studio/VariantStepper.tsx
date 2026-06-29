"use client";
import { totalVariants } from "@/lib/files";

interface VariantStepperProps {
  value: number;
  onChange: (val: number) => void;
  min?: number;
  fileCount: number;
}

export function VariantStepper({ value, onChange, min = 1, fileCount }: VariantStepperProps) {
  const total = totalVariants(fileCount, value);

  function decrement() {
    if (value > min) onChange(value - 1);
  }
  function increment() {
    onChange(value + 1);
  }

  const btnStyle: React.CSSProperties = {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: "#1c1c28",
    border: "1px solid var(--color-line)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
    color: "var(--color-text)",
    cursor: "pointer",
    userSelect: "none",
    fontWeight: 700,
    lineHeight: 1,
  };

  return (
    <div
      style={{
        flex: 1,
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
          margin: "0 0 6px",
          fontWeight: 700,
        }}
      >
        2 · Variants each
      </p>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 26, fontWeight: 800 }}>{value}</div>
        <div style={{ display: "flex", gap: 6 }}>
          <button style={btnStyle} onClick={decrement} aria-label="Decrease variants">
            –
          </button>
          <button style={btnStyle} onClick={increment} aria-label="Increase variants">
            +
          </button>
        </div>
      </div>
      <div style={{ fontSize: 10.5, color: "var(--color-muted2)", marginTop: 6 }}>
        {fileCount > 0
          ? `per video · ${fileCount} clip${fileCount !== 1 ? "s" : ""} → ${total} total`
          : "per video · add clips above"}
      </div>
    </div>
  );
}
