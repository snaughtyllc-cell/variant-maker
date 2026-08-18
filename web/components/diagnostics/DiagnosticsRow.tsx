"use client";
import { useState } from "react";
import { DiagnosticsItem, VariantOut } from "@/lib/types";
import { variantUrl, regenerate } from "@/lib/api";
import { diagnosticsReason } from "@/lib/format";
import { VariantSheet } from "@/components/variant/VariantSheet";

const MAX_REROLLS = 3;

interface DiagnosticsRowProps {
  item: DiagnosticsItem;
  onRegenerate: () => void;
}

export function DiagnosticsRow({ item, onRegenerate }: DiagnosticsRowProps) {
  const [inspecting, setInspecting] = useState(false);
  const [manifestOpen, setManifestOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const reason = diagnosticsReason(item);
  const isCorrupt = item.status === "corrupt";
  const padded = `v${String(item.index).padStart(2, "0")}`;
  const regenCount = item.quality.regen_count ?? 0;

  // Build single-variant VariantOut for Inspect sheet
  const sheetVariant: VariantOut = {
    index: item.index,
    filename: item.filename,
    status: item.status,
    quality: item.quality,
    file_url: variantUrl(item.source_id, item.filename),
  };

  async function handleRegenerate() {
    if (busy) return;
    setBusy(true);
    try {
      await regenerate(item.source_id, 1);
      onRegenerate();
    } catch (e) {
      console.error("Regenerate failed", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 14,
          background: "var(--color-panel)",
          border: "1px solid var(--color-line)",
          borderRadius: 12,
          padding: "12px 14px",
          marginBottom: 9,
        }}
      >
        {/* Thumbnail or dead placeholder */}
        <div
          style={{
            width: 38,
            height: 54,
            borderRadius: 7,
            flexShrink: 0,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {isCorrupt ? (
            <div
              style={{
                width: "100%",
                height: "100%",
                background: "#141019",
                border: "1px dashed #3a2630",
                borderRadius: 7,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#7a4a55",
                fontSize: 14,
              }}
            >
              ⚠
            </div>
          ) : (
            <video
              src={variantUrl(item.source_id, item.filename)}
              muted
              playsInline
              preload="metadata"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
                background: "#1e1e2a",
              }}
            />
          )}
        </div>

        {/* Variant index */}
        <div
          style={{
            flexShrink: 0,
            width: 54,
            fontWeight: 800,
            fontSize: 13,
            color: "var(--color-text)",
          }}
        >
          {padded}
        </div>

        {/* Status badge */}
        {isCorrupt ? (
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "3px 9px",
              borderRadius: 999,
              flexShrink: 0,
              color: "#fca5a5",
              background: "#2c1212",
              border: "1px solid #5a1f1f",
            }}
          >
            CORRUPT
          </span>
        ) : (
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "3px 9px",
              borderRadius: 999,
              flexShrink: 0,
              color: "#ffd08a",
              background: "#2c2210",
              border: "1px solid #5a4416",
            }}
          >
            BELOW FLOOR
          </span>
        )}

        {/* Reason + metric */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color: "var(--color-text)" }}>{reason.title}</div>
          <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 2 }}>
            {/* Split metric string so we can colour the number */}
            <MetricLine metric={reason.metric} corrupt={reason.corrupt} />
          </div>
        </div>

        {/* Re-roll counter */}
        <div
          style={{
            fontSize: 11,
            color: "var(--color-muted2)",
            flexShrink: 0,
          }}
        >
          ↻ {regenCount}/{MAX_REROLLS}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: 7, flexShrink: 0 }}>
          {/* Inspect — only for best_effort */}
          {!isCorrupt && (
            <button
              onClick={() => setInspecting(true)}
              style={{
                fontSize: 11.5,
                fontWeight: 700,
                padding: "7px 11px",
                borderRadius: 8,
                border: "1px solid var(--color-line)",
                background: "#16161f",
                color: "var(--color-text)",
                cursor: "pointer",
              }}
            >
              Inspect
            </button>
          )}

          {/* Manifest — JSON disclosure */}
          <button
            onClick={() => setManifestOpen((o) => !o)}
            style={{
              fontSize: 11.5,
              fontWeight: 700,
              padding: "7px 11px",
              borderRadius: 8,
              border: "1px solid var(--color-line)",
              background: "#16161f",
              color: "var(--color-text)",
              cursor: "pointer",
            }}
          >
            {"{ } Manifest"}
          </button>

          {/* Regenerate */}
          <button
            onClick={handleRegenerate}
            disabled={busy}
            style={{
              fontSize: 11.5,
              fontWeight: 700,
              padding: "7px 11px",
              borderRadius: 8,
              border: "none",
              background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              color: "#fff",
              cursor: busy ? "not-allowed" : "pointer",
              boxShadow: "0 3px 12px #ff4d8d33",
              opacity: busy ? 0.7 : 1,
            }}
          >
            {busy ? "…" : "↻ Regenerate"}
          </button>
        </div>
      </div>

      {/* Inline manifest disclosure */}
      {manifestOpen && (
        <div
          style={{
            marginTop: -5,
            marginBottom: 9,
            padding: "10px 14px",
            background: "#0d0d13",
            border: "1px solid var(--color-line2)",
            borderRadius: 10,
            fontSize: 11,
            fontFamily: "var(--font-geist-mono, monospace)",
            color: "var(--color-muted)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {JSON.stringify(item, null, 2)}
        </div>
      )}

      {/* Inspect sheet — single-variant, no nav */}
      {inspecting && !isCorrupt && (
        <VariantSheet
          sourceId={item.source_id}
          sourceName={item.filename.replace(/\.[^.]+$/, "")}
          variants={[sheetVariant]}
          index={0}
          onClose={() => setInspecting(false)}
          onNav={() => {}}
          onRegenerate={onRegenerate}
        />
      )}
    </>
  );
}

/** Renders the metric string, colouring the numeric value amber or red. */
function MetricLine({ metric, corrupt }: { metric: string; corrupt: boolean }) {
  // Find numeric token(s) in the metric string and colour them
  // e.g. "VMAF 84.2 < floor 90 · histogram OK"
  // or   "Spatial VMAF 22.0 < corruption floor · rejected before delivery"
  const parts = metric.split(/(\d+\.?\d*)/);
  const accentColor = corrupt ? "#fca5a5" : "#ffd08a";

  return (
    <>
      {parts.map((part, i) =>
        /^\d+\.?\d*$/.test(part) ? (
          <span key={i} style={{ color: accentColor, fontWeight: 700 }}>
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}
