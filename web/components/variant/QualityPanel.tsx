"use client";
import { Quality } from "@/lib/types";
import { ESCALATED_TITLE, pct01, similarityFromUniqueness, vmafPass } from "@/lib/format";

interface QualityPanelProps {
  quality: Quality;
  uniqueness?: number | null;
  uniquenessStatus?: string | null;
  uniquenessTarget?: number | null;
  escalated?: boolean;
  bestEffort?: boolean;
}

function QRow({
  label,
  children,
  locked,
}: {
  label: string;
  children: React.ReactNode;
  locked?: boolean;
}) {
  return (
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
        opacity: locked ? 0.5 : 1,
      }}
    >
      <span
        style={{
          fontSize: 13,
          flexShrink: 0,
          width: 108,
          color: "var(--color-text)",
        }}
      >
        {label}
        {locked && (
          <span style={{ fontSize: 10, marginLeft: 4 }}>🔒</span>
        )}
      </span>
      {children}
    </div>
  );
}

function Meter({ pct, green, amber }: { pct: number; green?: boolean; amber?: boolean }) {
  const bg = green
    ? "linear-gradient(90deg, #22c55e, #7bf2a8)"
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

function OkBadge({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 800,
        color: ok ? "#7bf2a8" : "#f87171",
        background: ok ? "#0c2c1a" : "#2c1010",
        border: `1px solid ${ok ? "#16502f" : "#5a2020"}`,
        padding: "2px 7px",
        borderRadius: 6,
        flexShrink: 0,
      }}
    >
      {ok ? "✓ OK" : "✗ fail"}
    </span>
  );
}

export function QualityPanel({
  quality,
  uniqueness,
  uniquenessStatus,
  uniquenessTarget,
  escalated,
  bestEffort,
}: QualityPanelProps) {
  const pass = vmafPass(quality.vmaf);
  const rerollPct = (quality.regen_count / 3) * 100;
  const uniquenessPct = uniqueness != null ? pct01(uniqueness) : null;
  const uniquenessOk = uniquenessStatus === "ok";
  // Same SSIM-bits scale: similarity = 1 − uniqueness (lower better).
  const similarity = uniqueness != null ? similarityFromUniqueness(uniqueness) : null;
  const similarityPct = similarity != null ? pct01(similarity) : null;
  const similarityTarget =
    uniquenessTarget != null ? similarityFromUniqueness(uniquenessTarget) : null;
  // Green when uniqueness clears its target (implies similarity ≤ 1 − target).
  const similarityOk = uniquenessOk;

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
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span>Quality</span>
        {escalated && (
          <span
            title={ESCALATED_TITLE}
            style={{
              fontSize: 9.5,
              fontWeight: 800,
              padding: "2px 7px",
              borderRadius: 999,
              textTransform: "none",
              letterSpacing: 0,
              color: "#c7b8ff",
              background: "#1e1740",
              border: "1px solid #362a68",
            }}
          >
            ⚡ stronger uniqueness pass
          </span>
        )}
      </div>

      {/* best_effort warning — never claims detection evasion, only describes the render tradeoff */}
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
            color: "#ffd08a",
            background: "#1c1608",
            border: "1px solid #3a2c10",
            borderRadius: 8,
          }}
        >
          <span>⚠</span>
          <span>
            Best effort after 3 re-rolls — quality stayed under the floor. Optimized for
            uniqueness while keeping a clean look.
          </span>
        </div>
      )}

      {/* Uniqueness — higher better; vs original even for n=1. Pass ~38%. 1080 medium ~55–65%; usable 720 Fast ~40–50%. */}
      <QRow label="Uniqueness">
        {uniquenessPct != null ? (
          <>
            <Meter pct={uniquenessPct} green={uniquenessOk} amber={!uniquenessOk} />
            <span
              style={{
                fontSize: 12.5,
                fontWeight: 800,
                flexShrink: 0,
                color: uniquenessOk ? "#7bf2a8" : "#fbbf24",
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
      </QRow>
      {uniquenessPct != null && uniquenessTarget != null && (
        <div
          style={{
            fontSize: 10.5,
            color: "var(--color-muted2)",
            margin: "-4px 2px 8px",
          }}
        >
          target ≥ {pct01(uniquenessTarget)}% vs the original · 1080 medium ~55–65% · usable 720 ~40–50%
        </div>
      )}

      {/* Similarity — same scale, lower better */}
      <QRow label="Similarity">
        {similarityPct != null ? (
          <>
            <Meter pct={similarityPct} green={similarityOk} amber={!similarityOk} />
            <span
              style={{
                fontSize: 12.5,
                fontWeight: 800,
                flexShrink: 0,
                color: similarityOk ? "#7bf2a8" : "#fbbf24",
              }}
            >
              {similarityPct}%
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
      </QRow>
      {similarityPct != null && similarityTarget != null && (
        <div
          style={{
            fontSize: 10.5,
            color: "var(--color-muted2)",
            margin: "-4px 2px 8px",
          }}
        >
          target ≤ {pct01(similarityTarget)}% (lower better · 1 − uniqueness)
        </div>
      )}

      {/* VMAF */}
      <QRow label="VMAF">
        <Meter pct={quality.vmaf} green={pass} />
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 800,
            flexShrink: 0,
            color: pass ? "#7bf2a8" : "#f87171",
          }}
        >
          {quality.vmaf.toFixed(1)}
        </span>
      </QRow>

      {/* Spatial guard */}
      <QRow label="Spatial guard">
        {quality.spatial_ok === null ? (
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
        ) : (
          <>
            <Meter pct={quality.spatial_vmaf ?? 0} green={quality.spatial_ok} />
            {quality.spatial_ok ? (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  color: "#7bf2a8",
                  background: "#0c2c1a",
                  border: "1px solid #16502f",
                  padding: "2px 7px",
                  borderRadius: 6,
                  flexShrink: 0,
                }}
              >
                ✓ no corruption
              </span>
            ) : (
              <OkBadge ok={false} />
            )}
          </>
        )}
      </QRow>

      {/* Histogram */}
      <QRow label="Histogram">
        <Meter pct={quality.histogram_ok ? 100 : 0} green={quality.histogram_ok} />
        <OkBadge ok={quality.histogram_ok} />
      </QRow>

      {/* Re-rolls */}
      <QRow label="Re-rolls">
        <Meter pct={rerollPct} amber />
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 800,
            flexShrink: 0,
            color: "#fbbf24",
          }}
        >
          {quality.regen_count} / 3
        </span>
      </QRow>
    </div>
  );
}
