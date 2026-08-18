"use client";
import { ENGINE_WAIT_HEADING, ENGINE_WAIT_LINES } from "@/lib/engineWaitCopy";

export function EngineWaitNote() {
  return (
    <div
      style={{
        margin: "0 0 14px",
        padding: "10px 12px",
        background: "var(--color-panel2)",
        border: "1px solid var(--color-line)",
        borderRadius: 10,
        fontSize: 12,
        lineHeight: 1.45,
        color: "var(--color-muted)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".5px",
          textTransform: "uppercase",
          color: "var(--color-muted2)",
          marginBottom: 6,
        }}
      >
        {ENGINE_WAIT_HEADING}
      </div>
      {ENGINE_WAIT_LINES.map((line) => (
        <p key={line} style={{ margin: "0 0 6px" }}>
          {line}
        </p>
      ))}
    </div>
  );
}
