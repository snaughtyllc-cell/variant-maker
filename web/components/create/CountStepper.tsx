"use client";
import { CREATE_COUNT_MAX, CREATE_COUNT_MIN } from "@/lib/createTypes";

interface CountStepperProps {
  value: number;
  onChange: (val: number) => void;
  disabled?: boolean;
}

export function CountStepper({ value, onChange, disabled }: CountStepperProps) {
  function decrement() {
    if (value > CREATE_COUNT_MIN) onChange(value - 1);
  }
  function increment() {
    if (value < CREATE_COUNT_MAX) onChange(value + 1);
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
    cursor: disabled ? "not-allowed" : "pointer",
    userSelect: "none",
    fontWeight: 700,
    lineHeight: 1,
    opacity: disabled ? 0.5 : 1,
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
        4 · Stills
      </p>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 26, fontWeight: 800 }}>{value}</div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            style={btnStyle}
            onClick={decrement}
            disabled={disabled || value <= CREATE_COUNT_MIN}
            aria-label="Decrease still count"
          >
            –
          </button>
          <button
            type="button"
            style={btnStyle}
            onClick={increment}
            disabled={disabled || value >= CREATE_COUNT_MAX}
            aria-label="Increase still count"
          >
            +
          </button>
        </div>
      </div>
      <div style={{ fontSize: 10.5, color: "var(--color-muted2)", marginTop: 6 }}>
        {CREATE_COUNT_MIN}–{CREATE_COUNT_MAX} stills per generate
      </div>
    </div>
  );
}
