"use client";
import { useEffect, useState } from "react";
import { SourceOut } from "@/lib/types";
import { regenerate, retryCopy, sourceUrl, sourceZipUrl, removeSource } from "@/lib/api";
import { copyMissingCopy, deliveryComplete, filesReadyCount, isFileReady, zipEmptyCopy, removePackCopy } from "@/lib/gallery";
import { shortfallCopy } from "@/lib/shortfallCopy";
import { okVariantKeys, selectionHasAllOk } from "@/lib/drive";
import {
  canShareVideoFiles,
  downloadVideoFiles,
  fetchVariantFiles,
  phoneShareHintCopy,
  readyShareableVariants,
  shareEmptyCopy,
  shareVideoFiles,
  shareVideosLabel,
  zipSecondaryCopy,
} from "@/lib/shareVideos";
import { postedCountCopy } from "@/lib/postUrl";
import { VariantCard } from "./VariantCard";

interface SourceGroupProps {
  source: SourceOut;
  onOpenVariant: (sourceId: string, index: number) => void;
  onRegenerate: () => void;
  selected: Set<string>;
  onToggleVariant: (key: string) => void;
  onToggleSelectSource: (source: SourceOut, select: boolean) => void;
  onRemove: () => void;
}

export function SourceGroup({
  source, onOpenVariant, onRegenerate, selected, onToggleVariant,   onToggleSelectSource,
  onRemove,
}: SourceGroupProps) {
  const [open, setOpen] = useState(true);
  const [regenLoading, setRegenLoading] = useState(false);
  const [copyLoading, setCopyLoading] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [zipMsg, setZipMsg] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [canShare, setCanShare] = useState(false);

  const hasShortfall = source.shortfall > 0;
  const filesReady = filesReadyCount(source);
  const fullDelivery = deliveryComplete(source);
  const stillRunning = source.job_state === "running" || !!source.in_flight;
  const shareable = readyShareableVariants(source.variants);
  const canSaveVideos = shareable.length > 0 && !stillRunning;

  useEffect(() => {
    setCanShare(canShareVideoFiles(typeof navigator === "undefined" ? undefined : navigator));
  }, []);
  const copyMissing = source.copy_status === "missing" && !stillRunning;
  const copyLanding = source.copy_status === "copying";
  const shortfallMsg = shortfallCopy(source);
  const postedCopy = postedCountCopy(
    source.variants.filter((v) => Boolean(v.post_url)).length,
  );

  // Compute avg VMAF
  const vmafValues = source.variants.map(v => v.quality.vmaf).filter(Boolean);
  const avgVmaf = vmafValues.length
    ? Math.round(vmafValues.reduce((a, b) => a + b, 0) / vmafValues.length)
    : null;

  // Spatial checks summary
  const spatialCount = source.variants.filter(v => v.quality.spatial_ok === true).length;
  const allSpatial = spatialCount === source.variants.length && source.variants.length > 0;

  async function handleSaveShare(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (stillRunning || shareBusy || shareable.length === 0) return;
    setShareBusy(true);
    setZipMsg(null);
    try {
      const files = await fetchVariantFiles(
        shareable.map((v) => ({ file_url: v.file_url, filename: v.filename })),
      );
      if (files.length === 0) {
        setZipMsg(shareEmptyCopy());
        return;
      }
      const nav = typeof navigator === "undefined" ? undefined : navigator;
      if (nav && typeof nav.share === "function" && canShareVideoFiles(nav, files)) {
        const share = nav.share.bind(nav);
        const result = await shareVideoFiles(files, (data) => share(data));
        if (result === "shared" || result === "aborted") return;
      }
      downloadVideoFiles(files);
    } catch {
      setZipMsg(shareEmptyCopy());
    } finally {
      setShareBusy(false);
    }
  }

  async function handleZip(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (stillRunning) return;
    setZipMsg(null);
    try {
      const res = await fetch(sourceZipUrl(source.source_id));
      if (!res.ok) {
        setZipMsg(zipEmptyCopy());
        return;
      }
      const blob = await res.blob();
      if (blob.size < 64) {
        setZipMsg(zipEmptyCopy());
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${source.source_id}_variants.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch {
      setZipMsg(zipEmptyCopy());
    }
  }

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

  async function handleRetryCopy() {
    if (copyLoading || stillRunning) return;
    setCopyLoading(true);
    try {
      await retryCopy(source.source_id);
      onRegenerate();
    } catch (e) {
      console.error("Retry copy failed", e);
    } finally {
      setCopyLoading(false);
    }
  }

  async function handleRemove(e: React.MouseEvent) {
    e.stopPropagation();
    if (removing) return;
    if (!window.confirm(removePackCopy(stillRunning))) return;
    setRemoving(true);
    try {
      await removeSource(source.source_id);
      onRemove();
    } catch (err) {
      console.error("Remove failed", err);
      setRemoving(false);
    }
  }

  const thumbReady = isFileReady(source.variants[0] ?? {});
  const thumbUrl = thumbReady ? source.variants[0]?.file_url : undefined;
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
            background: "#dce9eb",
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
            {postedCopy && ` · ${postedCopy}`}
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
                ? { color: "#247955", background: "#e9f8f0", border: "1px solid #c6e8d7" }
                : { color: "#8e6119", background: "#fff3e5", border: "1px solid #efd9b0" }),
            }}
          >
            {fullDelivery ? "✓ " : ""}
            {copyMissing
              ? `${filesReady} / ${source.requested} on Studio`
              : copyLanding
              ? `${filesReady} / ${source.requested} copying`
              : `${filesReady} / ${source.requested} delivered`}
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
          {canSaveVideos && (
            <button
              type="button"
              title={phoneShareHintCopy()}
              aria-label={shareVideosLabel(canShare)}
              onClick={handleSaveShare}
              disabled={shareBusy}
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: "var(--color-violet-l)",
                background: "#15101f",
                border: "1px solid #2c2748",
                padding: "7px 10px",
                minHeight: 36,
                borderRadius: 8,
                cursor: shareBusy ? "wait" : "pointer",
                opacity: shareBusy ? 0.7 : 1,
              }}
            >
              {shareBusy
                ? canShare
                  ? "Sharing…"
                  : "Saving…"
                : shareVideosLabel(canShare)}
            </button>
          )}
          {filesReady > 0 && !stillRunning && (
            <a
              href={sourceZipUrl(source.source_id)}
              download
              title={zipSecondaryCopy()}
              onClick={handleZip}
              style={{ fontSize: 11, color: "var(--color-muted)", textDecoration: "none" }}
            >
              Download ZIP
            </a>
          )}
          <span
            className="source-folder-link"
            style={{ fontSize: 12, color: "var(--color-violet-l)", textDecoration: "none" }}
          >
            ⌅ Open source folder
          </span>
          <button
            type="button"
            aria-label="Remove pack from Gallery"
            title="Remove from Gallery"
            onClick={handleRemove}
            disabled={removing}
            className="touch-hit"
            style={{
              width: 44,
              height: 44,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22,
              lineHeight: 1,
              fontWeight: 700,
              color: "var(--color-muted)",
              background: "transparent",
              border: "1px solid var(--color-line)",
              borderRadius: 8,
              cursor: removing ? "wait" : "pointer",
              opacity: removing ? 0.6 : 1,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>
      </div>

      {/* Shortfall bar — ONLY when shortfall > 0 */}
      {zipMsg && (
        <div
          style={{
            padding: "10px 16px",
            background: "#fff8eb",
            borderBottom: "1px solid #efdfbd",
            fontSize: 12.5,
            color: "#8e6119",
          }}
        >
          ⚠ {zipMsg}
        </div>
      )}
      {copyMissing && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 16px",
            background: "#fff8eb",
            borderBottom: "1px solid #efdfbd",
            fontSize: 12.5,
            color: "#8e6119",
            flexWrap: "wrap",
          }}
        >
          <span>⚠ {copyMissingCopy()}</span>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); handleRetryCopy(); }}
            disabled={copyLoading}
            style={{
              marginLeft: "auto",
              fontSize: 12.5,
              fontWeight: 700,
              color: "#fff",
              background: "var(--ink)",
              border: "none",
              padding: "7px 14px",
              borderRadius: 9,
              cursor: copyLoading ? "not-allowed" : "pointer",
              boxShadow: "none",
              opacity: copyLoading ? 0.7 : 1,
            }}
          >
            {copyLoading ? "Copying…" : "↻ Retry copy"}
          </button>
        </div>
      )}
      {copyLanding && !copyMissing && (
        <div
          style={{
            padding: "10px 16px",
            background: "#fff8eb",
            borderBottom: "1px solid #efdfbd",
            fontSize: 12.5,
            color: "#8e6119",
          }}
        >
          Videos are still landing on Studio…
        </div>
      )}
      {open && hasShortfall && shortfallMsg && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 16px",
            background: "#fff8eb",
            borderBottom: "1px solid #efdfbd",
            fontSize: 12.5,
            color: "#8e6119",
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
                background: "var(--ink)",
                border: "none",
                padding: "7px 14px",
                borderRadius: 9,
                cursor: regenLoading ? "not-allowed" : "pointer",
                boxShadow: "none",
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
