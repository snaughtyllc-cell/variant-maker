"use client";
import { useEffect, useRef } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { VariantOut } from "@/lib/types";
import { sourceUrl } from "@/lib/api";
import { isFileReady } from "@/lib/gallery";
import { VideoThumb } from "../common/VideoThumb";
import { CompareSlider } from "./CompareSlider";
import { ScrubBar } from "./ScrubBar";
import { CaptionBlock } from "./CaptionBlock";
import { QualityPanel } from "./QualityPanel";
import { VariantActions } from "./VariantActions";
import { variantWipeHint } from "@/lib/galleryLayout";

interface VariantSheetProps {
  sourceId: string;
  sourceName: string;
  variants: VariantOut[];
  index: number;
  onClose: () => void;
  onNav: (delta: number) => void;
  onRegenerate: () => void;
  /** In-pane Gallery review — packs stay visible; no dialog overlay. */
  embedded?: boolean;
  selectedCount?: number;
  flaggedCount?: number;
  packAvgPct?: number | null;
  onSendToDrive?: () => void;
}

function captionOf(v: { caption?: string | null }): string | null | undefined {
  return v.caption;
}

const navBtnStyle = (disabled: boolean): React.CSSProperties => ({
  width: 36,
  height: 36,
  borderRadius: 9,
  background: "#fff",
  border: "1px solid var(--color-line)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: disabled ? "var(--color-line2)" : "#23393e",
  cursor: disabled ? "not-allowed" : "pointer",
  flexShrink: 0,
  opacity: disabled ? 0.5 : 1,
});

export function VariantSheet({
  sourceId,
  sourceName,
  variants,
  index,
  onClose,
  onNav,
  onRegenerate,
  embedded = false,
  selectedCount,
  flaggedCount,
  packAvgPct,
  onSendToDrive,
}: VariantSheetProps) {
  // Create the two video refs here, pass to both CompareSlider and ScrubBar
  const beforeRef = useRef<HTMLVideoElement | null>(null);
  const afterRef = useRef<HTMLVideoElement | null>(null);

  const variant = variants[index];
  const isFirst = index <= 0;
  const isLast = index >= variants.length - 1;

  // Pad variant.index for display (v01, v02 …) — use the real 1-based variant.index
  const padded = String(variant.index).padStart(2, "0");

  // Keyboard: ← → for nav, Esc is handled by Radix Dialog
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (!isFirst) onNav(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (!isLast) onNav(+1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFirst, isLast, onNav]);

  if (!variant) return null;

  const body = (
    <div
      className="variant-sheet__body"
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: "auto",
        overflowX: "hidden",
        overscrollBehavior: "contain",
        WebkitOverflowScrolling: "touch",
      }}
    >
      <div className="variant-sheet__stage">
        <div className="variant-sheet__player">
          <CompareSlider
            beforeSrc={sourceUrl(sourceId)}
            afterSrc={variant.file_url}
            videoRefs={{ beforeRef, afterRef }}
            stage={embedded}
          />
          <div className="variant-sheet__player-hint">
            <span className="variant-sheet__hint-pill">{variantWipeHint()}</span>
          </div>
        </div>

        <div className="variant-sheet__scrub">
          <ScrubBar videos={[beforeRef, afterRef]} />
        </div>

        <div className="variant-sheet__filmstrip">
          <div className="variant-sheet__filmstrip-head">
            <div className="variant-sheet__filmstrip-label">
              Pack · {variants.length} variant{variants.length === 1 ? "" : "s"}
            </div>
            {(selectedCount != null || flaggedCount != null) && (
              <div className="variant-sheet__filmstrip-meta">
                {selectedCount ?? 0} selected · {flaggedCount ?? 0} flagged
              </div>
            )}
          </div>
          <div className="variant-sheet__filmstrip-row">
            {variants.map((v, i) => (
              <button
                key={v.index}
                type="button"
                className="variant-sheet__filmstrip-tile"
                data-current={i === index}
                onClick={() => onNav(i - index)}
                aria-label={`Go to variant ${String(v.index).padStart(2, "0")}`}
                aria-current={i === index}
              >
                {isFileReady(v) ? (
                  <VideoThumb src={v.file_url} className="variant-sheet__filmstrip-thumb" fill />
                ) : null}
                <span>{String(v.index).padStart(2, "0")}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="variant-sheet__panel">
        <div className="variant-sheet__panel-head">
          <div className="variant-sheet__panel-title">
            v{padded} <span>of {variants.length}</span>
          </div>
          <div className="variant-sheet__panel-sub">
            delivered
            {variant.uniqueness != null ? ` · ${Math.round(variant.uniqueness * 100)}% originality` : ""}
          </div>
        </div>
        <div className="variant-sheet__panel-body">
          <QualityPanel
            uniqueness={variant.uniqueness}
            uniquenessStatus={variant.uniqueness_status}
            bestEffort={variant.status === "best_effort"}
            packAvgPct={packAvgPct}
            heads={variant.quality.heads}
          />

          <div className="variant-sheet__hr" />

          <CaptionBlock caption={captionOf(variant)} />

          <div className="variant-sheet__hr" />

          <VariantActions
            sourceId={sourceId}
            variant={variant}
            onRegenerate={onRegenerate}
            onSendToDrive={onSendToDrive}
          />
        </div>
      </div>
    </div>
  );

  if (embedded) {
    return (
      <section className="gallery-review" aria-label="Variant review">
        {body}
      </section>
    );
  }

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        {/* Overlay — dims the Gallery behind */}
        <Dialog.Overlay
          className="variant-sheet-overlay"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 26, 30, 0.5)",
            backdropFilter: "blur(3px)",
            zIndex: 50,
            touchAction: "none",
          }}
        />

        {/* Panel — right-docked slide-over. Desktop: dark stage + 372px panel
            side by side. Mobile: full-screen, stage stacked above panel. */}
        <Dialog.Content
          aria-describedby={undefined}
          className="variant-sheet"
          onOpenAutoFocus={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => e.preventDefault()}
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: 430,
            maxWidth: "100vw",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            overscrollBehavior: "contain",
            zIndex: 51,
            outline: "none",
            animation: "vm-slidein 0.25s ease",
          }}
        >
          <style>{`
            @keyframes vm-slidein {
              from { transform: translateX(40px); opacity: 0.6; }
              to   { transform: none; opacity: 1; }
            }
          `}</style>

          {/* Header — row of ‹ title › ✕; never stacks, never scrolls away */}
          <div
            className="variant-sheet__header"
            style={{
              display: "flex",
              flexShrink: 0,
            }}
          >
            {/* Prev */}
            <button
              type="button"
              onClick={() => onNav(-1)}
              disabled={isFirst}
              aria-label="Previous variant"
              style={navBtnStyle(isFirst)}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18 }} aria-hidden="true">
                chevron_left
              </span>
            </button>

            {/* Title block */}
            <div style={{ flex: 1, minWidth: 0, padding: "0 4px" }}>
              <Dialog.Title
                style={{
                  fontFamily: "var(--font-brand)",
                  fontSize: 14.5,
                  fontWeight: 700,
                  letterSpacing: "-0.01em",
                  color: "var(--color-text)",
                  margin: 0,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {sourceName} · v{padded}
              </Dialog.Title>
              <span
                style={{
                  display: "block",
                  fontFamily: "var(--font-space-grotesk), monospace",
                  fontSize: 10.5,
                  color: "var(--color-muted2)",
                  marginTop: 2,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                variant {index + 1} of {variants.length} · {variant.filename}
              </span>
            </div>

            {/* Next */}
            <button
              type="button"
              onClick={() => onNav(+1)}
              disabled={isLast}
              aria-label="Next variant"
              style={navBtnStyle(isLast)}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18 }} aria-hidden="true">
                chevron_right
              </span>
            </button>

            {/* Close */}
            <Dialog.Close
              type="button"
              aria-label="Close"
              style={{
                width: 36,
                height: 36,
                marginLeft: 4,
                borderRadius: 9,
                background: "transparent",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-muted)",
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 20 }} aria-hidden="true">
                close
              </span>
            </Dialog.Close>
          </div>

          {body}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
