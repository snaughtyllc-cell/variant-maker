"use client";
import { useEffect, useRef } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { VariantOut } from "@/lib/types";
import { sourceUrl } from "@/lib/api";
import { CompareSlider } from "./CompareSlider";
import { ScrubBar } from "./ScrubBar";
import { QualityPanel } from "./QualityPanel";
import { VariantActions } from "./VariantActions";

interface VariantSheetProps {
  sourceId: string;
  sourceName: string;
  variants: VariantOut[];
  index: number;
  onClose: () => void;
  onNav: (delta: number) => void;
  onRegenerate: () => void;
}

export function VariantSheet({
  sourceId,
  sourceName,
  variants,
  index,
  onClose,
  onNav,
  onRegenerate,
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

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        {/* Overlay — dims the Gallery behind */}
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(23, 42, 46, 0.32)",
            backdropFilter: "blur(3px)",
            zIndex: 50,
          }}
        />

        {/* Panel — right-docked slide-over */}
        <Dialog.Content
          aria-describedby={undefined}
          className="variant-sheet"
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: 430,
            background: "#fbfdfd",
            borderLeft: "1px solid #c7dde0",
            boxShadow: "-20px 0 50px rgba(22, 58, 65, 0.22)",
            display: "flex",
            flexDirection: "column",
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

          {/* Header — above the video layer; padded out of the iPhone status bar */}
          <div className="variant-sheet__header">
            {/* Prev */}
            <button
              type="button"
              onClick={() => onNav(-1)}
              disabled={isFirst}
              aria-label="Previous variant"
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: "#f3f8f9",
                border: "1px solid var(--color-line)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: isFirst ? "var(--color-muted2)" : "var(--color-muted)",
                fontSize: 22,
                cursor: isFirst ? "not-allowed" : "pointer",
                flexShrink: 0,
                opacity: isFirst ? 0.4 : 1,
              }}
            >
              ‹
            </button>

            {/* Title block */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <Dialog.Title
                style={{
                  fontSize: 14.5,
                  fontWeight: 700,
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
                  fontSize: 11,
                  color: "var(--color-muted)",
                  marginTop: 1,
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
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: "#f3f8f9",
                border: "1px solid var(--color-line)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: isLast ? "var(--color-muted2)" : "var(--color-muted)",
                fontSize: 22,
                cursor: isLast ? "not-allowed" : "pointer",
                flexShrink: 0,
                opacity: isLast ? 0.4 : 1,
              }}
            >
              ›
            </button>

            {/* Close */}
            <Dialog.Close
              type="button"
              aria-label="Close"
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: "transparent",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-muted)",
                fontSize: 18,
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              ✕
            </Dialog.Close>
          </div>

          {/* Body — scrollable; minHeight 0 so iOS actually scrolls past the video */}
          <div className="variant-sheet__body">
            {/* Compare slider — beforeRef/afterRef wired in from sheet */}
            <CompareSlider
              beforeSrc={sourceUrl(sourceId)}
              afterSrc={variant.file_url}
              videoRefs={{ beforeRef, afterRef }}
            />

            {variant.look_src_url && variant.look_var_url && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 8,
                  marginTop: 12,
                }}
              >
                <figure style={{ margin: 0 }}>
                  <img
                    src={variant.look_src_url}
                    alt="Source still"
                    style={{
                      width: "100%",
                      display: "block",
                      borderRadius: 8,
                      aspectRatio: "9 / 16",
                      objectFit: "cover",
                      background: "#0e0e14",
                    }}
                  />
                  <figcaption style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 4 }}>
                    Source
                  </figcaption>
                </figure>
                <figure style={{ margin: 0 }}>
                  <img
                    src={variant.look_var_url}
                    alt="Variant still"
                    style={{
                      width: "100%",
                      display: "block",
                      borderRadius: 8,
                      aspectRatio: "9 / 16",
                      objectFit: "cover",
                      background: "#0e0e14",
                    }}
                  />
                  <figcaption style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 4 }}>
                    Variant
                  </figcaption>
                </figure>
              </div>
            )}

            {/* Scrub bar — controls both videos in sync */}
            <div style={{ marginTop: 12 }}>
              <ScrubBar videos={[beforeRef, afterRef]} />
            </div>

            {/* Quality rows */}
            <QualityPanel
              quality={variant.quality}
              uniqueness={variant.uniqueness}
              uniquenessStatus={variant.uniqueness_status}
              uniquenessTarget={variant.uniqueness_target}
              escalated={variant.escalated}
              bestEffort={variant.status === "best_effort"}
              lookStatus={variant.look_status}
              lookMae={variant.look_mae}
            />

            {/* Actions */}
            <VariantActions
              sourceId={sourceId}
              variant={variant}
              onRegenerate={onRegenerate}
            />

            {/* Bottom breathing room */}
            <div style={{ height: 24 }} />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
