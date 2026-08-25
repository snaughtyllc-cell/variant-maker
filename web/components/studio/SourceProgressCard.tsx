"use client";
import { SourceProgress } from "@/lib/progress";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Badge } from "@/components/common/Badge";
import { VideoThumb } from "@/components/common/VideoThumb";
import { QualityMode, inFlightLookingLabel, inFlightRenderingLabel } from "@/lib/hqWaitCopy";
import { ESCALATED_TITLE } from "@/lib/format";

interface SourceProgressCardProps {
  source: SourceProgress;
  qualityMode?: QualityMode;
}

export function SourceProgressCard({ source, qualityMode = "fast" }: SourceProgressCardProps) {
  const { filename, requested, delivered, done, inFlight, lookPreview, variants } = source;
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
          {inFlightRenderingLabel(index, qualityMode)}
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
    if (state === "looking") {
      return (
        <span style={{ color: "var(--color-cyan)" }}>
          {inFlightLookingLabel(index)}
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
          ? "0 0 0 1px #16c8d322, 0 8px 26px #00000040"
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

      {lookPreview && (lookPreview.src || lookPreview.var) && (
        <div
          data-testid="look-preview"
          style={{
            marginTop: 10,
            padding: 8,
            borderRadius: 10,
            border: `1px solid ${lookPreview.status === "fail" ? "#5a2a28" : "var(--color-line2)"}`,
            background: "#14141d",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 800,
              color:
                lookPreview.status === "fail"
                  ? "#f0a8a4"
                  : lookPreview.status === "ok"
                    ? "#7bf2a8"
                    : "var(--color-cyan)",
              marginBottom: 6,
            }}
          >
            {lookPreview.status === "fail"
              ? "Look fail"
              : lookPreview.status === "ok"
                ? "Look ok"
                : "Looking…"}
            {lookPreview.mae != null ? ` · MAE ${lookPreview.mae}` : ""}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
            }}
          >
            {lookPreview.src ? (
              <figure style={{ margin: 0 }}>
                <img
                  src={lookPreview.src}
                  alt="Source"
                  style={{
                    width: "100%",
                    display: "block",
                    borderRadius: 6,
                    aspectRatio: "9 / 16",
                    objectFit: "cover",
                    background: "#0e0e14",
                  }}
                />
                <figcaption style={{ fontSize: 10, color: "var(--color-muted2)", marginTop: 4 }}>
                  Source
                </figcaption>
              </figure>
            ) : null}
            {lookPreview.var ? (
              <figure style={{ margin: 0 }}>
                <img
                  src={lookPreview.var}
                  alt="Variant"
                  style={{
                    width: "100%",
                    display: "block",
                    borderRadius: 6,
                    aspectRatio: "9 / 16",
                    objectFit: "cover",
                    background: "#0e0e14",
                  }}
                />
                <figcaption style={{ fontSize: 10, color: "var(--color-muted2)", marginTop: 4 }}>
                  Variant
                </figcaption>
              </figure>
            ) : null}
          </div>
        </div>
      )}

      {/* Thumbs + in-flight slot (show the dashed tile during v01 too) */}
      {(variants.length > 0 || inFlight) && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6, 1fr)",
            alignItems: "start",
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
                    {v.escalated && (
                      <span title={ESCALATED_TITLE}>
                        <Badge color="cyan">⚡</Badge>
                      </span>
                    )}
                    {isBestEffort && <Badge color="amber">best effort</Badge>}
                  </div>
                }
              />
            );
          })}

          {/* Unknown aspect until the file exists — keep a 9:16 dashed slot */}
          {inFlight && (
            <div
              style={{
                aspectRatio: "9 / 16",
                width: "100%",
                alignSelf: "start",
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
                  : inFlight.state === "looking"
                  ? "look"
                  : inFlight.state === "uniqueness"
                  ? "⟡ unique"
                  : inFlight.state === "escalating"
                  ? "⚡ escalate"
                  : qualityMode === "hq"
                  ? "HQ"
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
