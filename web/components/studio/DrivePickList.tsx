"use client";
import type { DrivePick } from "./DrivePickerModal";

interface DrivePickListProps {
  picks: DrivePick[];
  onRemove: (index: number) => void;
}

function thumbGradient(name: string): string {
  const gradients = [
    "linear-gradient(135deg,#0ea5e9,#1f2937)",
    "linear-gradient(135deg,#7c3aed,#831843)",
    "linear-gradient(135deg,#22d3ee,#0e7490)",
    "linear-gradient(135deg,#34d399,#064e3b)",
    "linear-gradient(135deg,#f59e0b,#7c2d12)",
    "linear-gradient(135deg,#a78bfa,#3b0764)",
    "linear-gradient(135deg,#fb7185,#831843)",
  ];
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return gradients[h % gradients.length];
}

export function DrivePickList({ picks, onRemove }: DrivePickListProps) {
  if (picks.length === 0) return null;

  return (
    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
      {picks.map((pick, i) => (
        <div
          key={`${pick.id}-${i}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 11,
            background: "var(--color-panel2)",
            border: "1px solid var(--color-line)",
            borderRadius: 10,
            padding: "9px 11px",
          }}
        >
          <div
            style={{
              width: 42,
              height: 30,
              borderRadius: 6,
              flexShrink: 0,
              background: thumbGradient(pick.name),
            }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <b
              style={{
                fontSize: 13,
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {pick.name}
            </b>
            <span style={{ display: "block", fontSize: 11, color: "var(--color-muted)" }}>
              Google Drive
            </span>
          </div>
          <button
            onClick={() => onRemove(i)}
            className="touch-hit"
            style={{
              background: "none",
              border: "none",
              color: "var(--color-muted2)",
              fontSize: 16,
              cursor: "pointer",
              padding: "0 8px",
              lineHeight: 1,
            }}
            aria-label={`Remove ${pick.name}`}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
