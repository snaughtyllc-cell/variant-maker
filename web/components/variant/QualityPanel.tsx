"use client";
import { pct01 } from "@/lib/format";
import type { QualityHead } from "@/lib/types";
import {
  uniquenessCoverageChips,
  uniquenessCoverageSubcopy,
  uniquenessCustomerLabel,
} from "@/lib/prepareCopy";

interface QualityPanelProps {
  uniqueness?: number | null;
  uniquenessStatus?: string | null;
  bestEffort?: boolean;
  heads?: Record<string, QualityHead | null | undefined> | null;
}

function Meter({ pct, green, amber, red }: { pct: number; green?: boolean; amber?: boolean; red?: boolean }) {
  const bg = green
    ? "linear-gradient(90deg, #22c55e, #7bf2a8)"
    : red
    ? "linear-gradient(90deg, #ef4444, #f0a8a4)"
    : amber
    ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
    : "#3a3a4a";
  return (
    <div
      style={{
        flex: 1,
        height: 6,
        borderRadius: 99,
        background: "#20202c",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "block",
          height: "100%",
          width: `${Math.min(100, Math.max(0, pct))}%`,
          borderRadius: 99,
          backgroundImage: bg,
        }}
      />
    </div>
  );
}

export function QualityPanel({
  uniqueness,
  uniquenessStatus,
  bestEffort,
  heads,
}: QualityPanelProps) {
  const uniquenessPct = uniqueness != null ? pct01(uniqueness) : null;
  const uniquenessOk = uniquenessStatus === "ok";
  const uniquenessFloorFail = uniquenessStatus === "below_floor";
  const coverage = uniquenessCoverageChips(uniqueness, heads);

  return (
    <div>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.7px",
          color: "var(--color-muted2)",
          fontWeight: 700,
          margin: "20px 0 10px",
        }}
      >
        {uniquenessCustomerLabel()}
      </div>

      {bestEffort && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            padding: "9px 11px",
            marginBottom: 10,
            fontSize: 11.5,
            lineHeight: 1.5,
            color: "#8e6119",
            background: "#fff8eb",
            border: "1px solid #efdfbd",
            borderRadius: 8,
          }}
        >
          <span>⚠</span>
          <span>This copy needed extra processing.</span>
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "11px 12px",
          background: "var(--color-panel2)",
          border: "1px solid var(--color-line)",
          borderRadius: 10,
          marginBottom: 8,
        }}
      >
        {uniquenessPct != null ? (
          <>
            <Meter pct={uniquenessPct} green={uniquenessOk} amber={!uniquenessOk && !uniquenessFloorFail} red={uniquenessFloorFail} />
            <span
              style={{
                fontSize: 12.5,
                fontWeight: 800,
                flexShrink: 0,
                color: uniquenessOk ? "#247955" : uniquenessFloorFail ? "#a33f3d" : "#a56b17",
              }}
            >
              {uniquenessPct}%
            </span>
          </>
        ) : (
          <>
            <Meter pct={0} />
            <span
              style={{
                fontSize: 12.5,
                fontWeight: 800,
                flexShrink: 0,
                color: "var(--color-muted)",
              }}
            >
              — / n/a
            </span>
          </>
        )}
      </div>

      <p
        style={{
          margin: "0 0 8px",
          fontSize: 11.5,
          lineHeight: 1.45,
          color: "var(--color-muted)",
        }}
      >
        {uniquenessCoverageSubcopy()}
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
        }}
      >
        {coverage.map((chip) => {
          const scored = chip.state === "scored";
          return (
            <span
              key={chip.kind}
              title={chip.title}
              data-coverage-chip={chip.kind}
              data-coverage-state={chip.state}
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: "3px 7px",
                borderRadius: 6,
                lineHeight: 1.4,
                background: scored ? "#e7f7f8" : "transparent",
                color: scored ? "#075966" : "var(--color-muted2)",
                border: `1px solid ${scored ? "#b7e4e8" : "var(--color-line)"}`,
              }}
            >
              {chip.text}
            </span>
          );
        })}
      </div>
    </div>
  );
}
