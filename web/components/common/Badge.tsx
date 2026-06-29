"use client";
import { ReactNode } from "react";

type BadgeColor = "green" | "amber" | "cyan" | "red" | "muted";

interface BadgeProps {
  children: ReactNode;
  color?: BadgeColor;
  className?: string;
}

const COLOR_MAP: Record<BadgeColor, { bg: string; color: string; border: string }> = {
  green:  { bg: "#0b3d1f", color: "#7bf2a8", border: "#134d28" },
  amber:  { bg: "#3d2200", color: "#f59e0b", border: "#4d2e00" },
  cyan:   { bg: "#072830", color: "#22d3ee", border: "#0c3d47" },
  red:    { bg: "#2a0e0e", color: "#f87171", border: "#5a1a1a" },
  muted:  { bg: "#14141d", color: "#8a8aa0", border: "#23232f" },
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
