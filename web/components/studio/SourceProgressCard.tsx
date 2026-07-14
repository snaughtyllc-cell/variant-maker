"use client";
import { SourceProgress } from "@/lib/progress";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Badge } from "@/components/common/Badge";
import { VideoThumb } from "@/components/common/VideoThumb";

interface SourceProgressCardProps {
  source: SourceProgress;
}

export function SourceProgressCard({ source }: SourceProgressCardProps) {
  const { filename, requested, delivered, done, inFlight, variants } = source;
  const progress = requested > 0 ? done / requested : 0;
  const isActive = !!inFlight;

  // Status line: can show a live rendering/checking line + a rerolling line simultaneously
  // because inFlight only tracks the most recent event, we render based on its state
  const renderStatusLine = () => {
    if (!inFlight) return null;

    const { index, state, attempt, max_attempts } = inFlight;
    const idxStr = String(index).padStart(2, "0");

    if (state === "rendering") {
      return (
        <span style={{ color: "var(--color-cyan)" }}>
          ● v{idxStr} rendering…
        </span>
      );
    }
    if (state === "checking") {
      return (
        <span style={{ color: "var(--color-cyan)" }}>
          ● v{idxStr} checking…
        </span>
      );
    }
    if (state === "rerolling") {
      return (
        <>
          <span style={{ color: "var(--color-amber)" }}>
            ↻ v{idxStr} re-rolling {attempt}/{max_attempts}
          </span>
        </>
      );
    }
    if (state === "uniqueness") {
      return (
        <span style={{ color: "var(--color-cyan)" }}>
          ⟡ v{idxStr} checking uniqueness…
        </span>
      );
    }
    if (state === "escalating") {
      return (
        <span style={{ color: "#c7b8ff" }}>
          ⚡ v{idxStr} escalating strength…
        </span>
      );
    }
    return null;
  };

  return (
    <div
      style={{
        background: "var(--color-panel)",
        border: `1px solid ${isActive ? "#2f2a52" : "var(--color-line)"}`,
        borderRadius: 13,
        padding: 14,
        marginBottom: 13,
        boxShadow: isActive
          ? "0 0 0 1px #7c5cff22, 0 8px 26px #00000040"
          : "none",
        transition: "border-color 0.2s, box-shadow 0.2s",
      }}
    >
      {/* Header: thumb placeholder + filename + count */}
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        {/* Thumbnail placeholder — 16:9 aspect for the source preview */}
        <div
          style={{
            width: 48,
            height: 34,
            borderRadius: 7,
            flex: "none",
            background: "linear-gradient(135deg, #1c1430, #241a44)",
            border: "1px solid var(--color-line2)",
          }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 13.5,
              fontWeight: 700,
              color: "var(--color-text)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {filename}
          </div>
        </div>
        {/* delivered / requested count */}
        <div style={{ fontSize: 13, fontWeight: 800, flexShrink: 0 }}>
          <span style={{ color: "var(--color-violet-l)" }}>{delivered}</span>
          <span style={{ color: "var(--color-muted)", fontWeight: 600 }}> / {requested}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ margin: "11px 0 9px" }}>
        <ProgressBar value={progress} />
      </div>

      {/* Status line */}
      <div
        style={{
          fontSize: 11.5,
          color: "var(--color-muted)",
          display: "flex",
          gap: 14,
          flexWrap: "wrap",
          alignItems: "center",
          minHeight: 16,
        }}
      >
        {renderStatusLine()}
        <span>{delivered} ready</span>
      </div>

      {/* Variant thumbnails grid — only render if any variants exist */}
      {variants.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6, 1fr)",
            gap: 6,
            marginTop: 11,
          }}
        >
          {variants.map((v) => {
            const vmaf = v.quality?.vmaf;
            const vmafRounded = vmaf != null ? Math.round(vmaf) : null;
            const badgeColor =
              vmafRounded == null ? "muted" : vmafRounded >= 93 ? "green" : vmafRounded >= 90 ? "amber" : "red";
            const uniquenessPct = v.uniqueness != null ? Math.round(v.uniqueness * 100) : null;
            const isBestEffort = v.status === "best_effort";
            return (
              <VideoThumb
                key={v.index}
                src={v.file_url}
                badge={
                  <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
                    {vmafRounded != null && <Badge color={badgeColor}>{vmafRounded}</Badge>}
                    {uniquenessPct != null && (
                      <Badge color={v.escalated ? "cyan" : "muted"}>{uniquenessPct}%</Badge>
                    )}
                    {v.escalated && <Badge color="cyan">⚡</Badge>}
                    {isBestEffort && <Badge color="amber">best effort</Badge>}
                  </div>
                }
              />
            );
          })}

          {/* Show in-flight slot if currently processing */}
          {inFlight && (
            <div
              style={{
                aspectRatio: "9 / 16",
                borderRadius: 6,
                background: "#14141d",
                border: "1px dashed var(--color-line2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span style={{ fontSize: 8, color: "var(--color-muted2)" }}>
                {inFlight.state === "rerolling"
                  ? `↻ ${inFlight.attempt}/${inFlight.max_attempts}`
                  : inFlight.state === "checking"
                  ? "check"
                  : inFlight.state === "uniqueness"
                  ? "⟡ unique"
                  : inFlight.state === "escalating"
                  ? "⚡ escalate"
                  : "render"}
              </span>
            </div>
          )}
        </div>
      )}

      {/* "N ready" cue — shown once at least one variant is delivered */}
      {delivered > 0 && (
        <div
          style={{
            marginTop: 6,
            fontSize: 11,
            color: "var(--color-muted2)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span style={{ color: "var(--color-violet-l)" }}>✦</span>
          {delivered} variant{delivered !== 1 ? "s" : ""} ready
        </div>
      )}
    </div>
  );
}
