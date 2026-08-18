"use client";
import { useState } from "react";
import { SourceOut } from "@/lib/types";
import { regenerate, sourceUrl, sourceZipUrl } from "@/lib/api";
import { shortfallCopy } from "@/lib/shortfallCopy";
import { okVariantKeys, selectionHasAllOk } from "@/lib/drive";
import { VariantCard } from "./VariantCard";

interface SourceGroupProps {
  source: SourceOut;
  onOpenVariant: (sourceId: string, index: number) => void;
  onRegenerate: () => void;
  selected: Set<string>;
  onToggleVariant: (key: string) => void;
  onToggleSelectSource: (source: SourceOut, select: boolean) => void;
}

export function SourceGroup({
  source, onOpenVariant, onRegenerate, selected, onToggleVariant, onToggleSelectSource,
}: SourceGroupProps) {
  const [open, setOpen] = useState(true);
  const [regenLoading, setRegenLoading] = useState(false);

  const hasShortfall = source.shortfall > 0;
  const fullDelivery = source.shortfall === 0;
  const stillRunning = source.job_state === "running" || !!source.in_flight;
  const shortfallMsg = shortfallCopy(source);

  // Compute avg VMAF
  const vmafValues = source.variants.map(v => v.quality.vmaf).filter(Boolean);
  const avgVmaf = vmafValues.length
    ? Math.round(vmafValues.reduce((a, b) => a + b, 0) / vmafValues.length)
    : null;

  // Spatial checks summary
  const spatialCount = source.variants.filter(v => v.quality.spatial_ok === true).length;
  const allSpatial = spatialCount === source.variants.length && source.variants.length > 0;

  async function handleRegenerate() {
    if (regenLoading || stillRunning) return;
    setRegenLoading(true);
    try {
      await regenerate(source.source_id, source.shortfall);
      onRegenerate();
    } catch (e) {
      console.error("Regenerate failed", e);
    } finally {
      setRegenLoading(false);
    }
  }

  const thumbUrl = source.variants[0]?.file_url;
  const thumbSrc = thumbUrl ?? sourceUrl(source.source_id);
  const okCount = okVariantKeys([source]).length;
  const sourceAllSelected = selectionHasAllOk(selected, [source]);
  const sourceSelectLabel = sourceAllSelected ? "Deselect" : `Select ${okCount}`;

  return (
    <div
      style={{
        background: "var(--color-panel)",
        border: "1px solid var(--color-line)",
        borderRadius: 14,
        marginBottom: 16,
        overflow: "hidden",
      }}
    >
      {/* Group header */}
      <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 13,
            padding: "14px 16px",
            borderBottom: "1px solid var(--color-line)",
            cursor: "pointer",
            userSelect: "none",
            flexWrap: "wrap",
          }}
        onClick={() => setOpen(o => !o)}
      >
        {/* Chevron */}
        <span
          style={{
            color: "var(--color-muted2)",
            fontSize: 12,
            transition: "transform 0.15s ease",
            transform: open ? "rotate(0deg)" : "rotate(-90deg)",
            display: "inline-block",
          }}
        >
          ▾
        </span>

        {/* Thumbnail */}
        <div
          style={{
            width: 46,
            height: 33,
            borderRadius: 7,
            flexShrink: 0,
            overflow: "hidden",
            background: "#14141d",
            border: "1px solid var(--color-line)",
          }}
        >
          {thumbUrl ? (
            <video
              src={thumbSrc}
              muted
              playsInline
              preload="metadata"
              style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            />
          ) : (
            <div style={{ width: "100%", height: "100%", background: "#1e1e2a" }} />
          )}
        </div>

        {/* Name + summary */}
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
            {source.filename}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 1 }}>
            {avgVmaf != null && `avg VMAF ${avgVmaf}`}
            {avgVmaf != null && " · "}
            {allSpatial && source.variants.length > 0
              ? "all spatial-checks passed"
              : spatialCount > 0
              ? `${spatialCount} of ${source.variants.length} passed spatial`
              : source.variants.length > 0
              ? "no spatial checks (Tier-1)"
              : "no variants yet"}
          </div>
        </div>

        {/* Right side: delivery pill + folder link */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              fontWeight: 700,
              padding: "4px 10px",
              borderRadius: 999,
              ...(fullDelivery
                ? { color: "#7bf2a8", background: "#0c2c1a", border: "1px solid #16502f" }
                : { color: "#ffd08a", background: "#2c2210", border: "1px solid #5a4416" }),
            }}
          >
            {fullDelivery ? "✓ " : ""}{source.delivered} / {source.requested} delivered
          </span>
          {okCount > 0 && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelectSource(source, !sourceAllSelected);
              }}
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: "var(--color-violet-l)",
                background: "#15101f",
                border: "1px solid #2c2748",
                padding: "7px 10px",
                minHeight: 36,
                borderRadius: 8,
                cursor: "pointer",
              }}
            >
              {sourceSelectLabel}
            </button>
          )}
          {source.delivered > 0 && (
            <a
              href={sourceZipUrl(source.source_id)}
              download
              onClick={(e) => e.stopPropagation()}
              style={{ fontSize: 12, color: "var(--color-violet-l)", textDecoration: "none" }}
            >
              ⬇ Download ZIP
            </a>
          )}
          <span
            className="source-folder-link"
            style={{ fontSize: 12, color: "var(--color-violet-l)", textDecoration: "none" }}
          >
            ⌅ Open source folder
          </span>
        </div>
      </div>

      {/* Shortfall bar — ONLY when shortfall > 0 */}
      {open && hasShortfall && shortfallMsg && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 16px",
            background: "#1c1608",
            borderBottom: "1px solid #3a2c10",
            fontSize: 12.5,
            color: "#ffd08a",
          }}
        >
          <span>⚠ {shortfallMsg}</span>
          {!stillRunning && (
            <button
              onClick={(e) => { e.stopPropagation(); handleRegenerate(); }}
              disabled={regenLoading}
              style={{
                marginLeft: "auto",
                fontSize: 12.5,
                fontWeight: 700,
                color: "#fff",
                background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
                border: "none",
                padding: "7px 14px",
                borderRadius: 9,
                cursor: regenLoading ? "not-allowed" : "pointer",
                boxShadow: "0 4px 14px #ff4d8d33",
                opacity: regenLoading ? 0.7 : 1,
              }}
            >
              {regenLoading ? "Regenerating…" : `↻ Regenerate ${source.shortfall}`}
            </button>
          )}
        </div>
      )}

      {/* Variant grid — 8-across responsive */}
      {open && (
        <div style={{ padding: 16 }}>
          <div className="grid grid-cols-3 min-[700px]:grid-cols-5 min-[1100px]:grid-cols-8 gap-2.5">
            {source.variants.map((variant) => {
              const key = `${source.source_id}:${variant.index}`;
              return (
                <VariantCard
                  key={variant.index}
                  variant={variant}
                  sourceId={source.source_id}
                  onOpen={() => onOpenVariant(source.source_id, variant.index)}
                  selected={selected.has(key)}
                  onToggle={() => onToggleVariant(key)}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
