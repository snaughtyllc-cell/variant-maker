"use client";

interface ProgressBarProps {
  value: number; // 0..1
}

export function ProgressBar({ value }: ProgressBarProps) {
  const pct = Math.min(1, Math.max(0, value)) * 100;
  return (
    <div
      style={{
        height: 7,
        borderRadius: 99,
        background: "#1b1b26",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${pct}%`,
          borderRadius: 99,
          backgroundImage: "var(--background-image-progress)",
          transition: "width 0.35s ease",
        }}
      />
    </div>
  );
}
