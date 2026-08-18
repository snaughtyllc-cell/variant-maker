"use client";
import { useRun } from "@/lib/runStore";
import { SourceProgressCard } from "./SourceProgressCard";

export function ProgressPanel() {
  const { jobId, progress, complete } = useRun();

  // Empty state — no job running
  if (!jobId) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          padding: "0 32px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            background: "linear-gradient(135deg, #1c1430, #241a44)",
            border: "1px solid #2e2350",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 20,
            marginBottom: 4,
          }}
        >
          ◈
        </div>
        <p
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: "var(--color-text)",
            margin: 0,
          }}
        >
          No run in progress
        </p>
        <p
          style={{
            fontSize: 12,
            color: "var(--color-muted2)",
            margin: 0,
            lineHeight: 1.5,
            maxWidth: 200,
          }}
        >
          Drop a video and hit Generate — progress shows here
        </p>
      </div>
    );
  }

  const sources = Object.values(progress.bySource);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Panel header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 14,
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
            {complete ? "Complete" : "Generating…"}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 2 }}>
            {complete
              ? "All variants done"
              : "Live status updates every second"}
          </div>
        </div>

        {/* Live / done pill */}
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#14141d",
            border: "1px solid var(--color-line)",
            fontSize: 11.5,
            color: "var(--color-muted)",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: complete ? "var(--color-green)" : "var(--color-cyan)",
              boxShadow: complete
                ? "0 0 8px #22c55e88"
                : "0 0 8px #22d3ee99",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          {complete ? "done" : "live"}
        </span>
      </div>

      {/* Source cards — scrollable */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {sources.map((source) => (
          <SourceProgressCard key={source.source_id} source={source} />
        ))}
      </div>
    </div>
  );
}
