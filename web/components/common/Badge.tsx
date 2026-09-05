"use client";
import { ReactNode } from "react";

type BadgeColor = "green" | "amber" | "cyan" | "red" | "muted";

interface BadgeProps {
  children: ReactNode;
  color?: BadgeColor;
  className?: string;
}

const COLOR_MAP: Record<BadgeColor, { bg: string; color: string; border: string }> = {
  green:  { bg: "#e9f8f0", color: "#247955", border: "#c6e8d7" },
  amber:  { bg: "#fff3e5", color: "#986317", border: "#efd9b0" },
  cyan:   { bg: "#dff4f5", color: "#075966", border: "#b9e7ea" },
  red:    { bg: "#fff3f1", color: "#a33f3d", border: "#efc5c0" },
  muted:  { bg: "#edf5f6", color: "#637277", border: "#d4e3e6" },
};

export function Badge({ children, color = "muted", className }: BadgeProps) {
  const { bg, color: textColor, border } = COLOR_MAP[color];
  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "1px 5px",
        borderRadius: 5,
        fontSize: 8,
        fontWeight: 800,
        background: bg,
        color: textColor,
        border: `1px solid ${border}`,
        lineHeight: 1.4,
        letterSpacing: "0.3px",
      }}
    >
      {children}
    </span>
  );
}
