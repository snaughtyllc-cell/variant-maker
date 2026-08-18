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
            background: "#05050880",
            backdropFilter: "blur(1px)",
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
            background: "linear-gradient(180deg, #0e0e15, #0b0b11)",
            borderLeft: "1px solid var(--color-line2)",
            boxShadow: "-20px 0 50px #000000aa",
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

          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "14px 16px",
              borderBottom: "1px solid var(--color-line)",
              flexShrink: 0,
            }}
          >
            {/* Prev */}
            <button
              onClick={() => onNav(-1)}
              disabled={isFirst}
              aria-label="Previous variant"
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: "#16161f",
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
              onClick={() => onNav(+1)}
              disabled={isLast}
              aria-label="Next variant"
              style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: "#16161f",
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
