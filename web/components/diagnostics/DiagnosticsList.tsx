"use client";
import { DiagnosticsItem } from "@/lib/types";
import { DiagnosticsRow } from "./DiagnosticsRow";

interface DiagnosticsListProps {
  items: DiagnosticsItem[];
  onRegenerate: () => void;
}

export function DiagnosticsList({ items, onRegenerate }: DiagnosticsListProps) {
  // Summary counts
  const belowFloorCount = items.filter((d) => d.status === "best_effort").length;
  const corruptCount = items.filter((d) => d.status === "corrupt").length;

  // Group by source_id, preserving insertion order
  const groups = new Map<string, { filename: string; items: DiagnosticsItem[] }>();
  for (const item of items) {
    if (!groups.has(item.source_id)) {
      groups.set(item.source_id, { filename: item.filename, items: [] });
    }
    // filename on DiagnosticsItem is the variant filename, not the source filename.
    // We use item.source_id as the group key; show source_id as the label since
    // the source filename is not carried on DiagnosticsItem directly.
    groups.get(item.source_id)!.items.push(item);
  }

  return (
    <div>
      {/* Summary chips — only shown when there are failures */}
      {items.length > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          <div
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 10,
              padding: "8px 13px",
              textAlign: "center",
            }}
          >
            <b
              style={{
                fontSize: 17,
                display: "block",
                color: "#8e6119",
              }}
            >
              {belowFloorCount}
            </b>
            <span style={{ fontSize: 10.5, color: "var(--color-muted)" }}>below floor</span>
          </div>
          <div
            style={{
              background: "var(--color-panel2)",
              border: "1px solid var(--color-line)",
              borderRadius: 10,
              padding: "8px 13px",
              textAlign: "center",
            }}
          >
            <b
              style={{
                fontSize: 17,
                display: "block",
                color: "#a33f3d",
              }}
            >
              {corruptCount}
            </b>
            <span style={{ fontSize: 10.5, color: "var(--color-muted)" }}>corrupt</span>
          </div>
        </div>
      )}

          {/* Empty state — the normal/happy state */}
      {items.length === 0 && (
        <div
          style={{
            marginTop: 14,
            padding: "14px 16px",
            border: "1px dashed var(--color-line2)",
            borderRadius: 12,
            color: "var(--color-muted)",
            fontSize: 12.5,
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#0d0d13",
          }}
        >
          <span style={{ fontSize: 18 }}>✓</span>
          <span>
            Nothing in Diagnostics — only best-effort / corrupt variants appear here.
            Incomplete runs show as shortfall on Gallery until they finish.
          </span>
        </div>
      )}

      {/* Groups */}
      {Array.from(groups.entries()).map(([sourceId, group]) => {
        const failed = group.items.length;
        return (
          <div key={sourceId}>
            {/* Source group header */}
            <div
              style={{
                fontSize: 12,
                color: "var(--color-muted)",
                margin: "10px 2px 9px",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <span>▾</span>
              <b style={{ color: "var(--color-text)" }}>{sourceId}</b>
              <span>· {failed} failed</span>
            </div>

            {/* Rows */}
            {group.items.map((item) => (
              <DiagnosticsRow
                key={`${item.source_id}-${item.index}`}
                item={item}
                onRegenerate={onRegenerate}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}
