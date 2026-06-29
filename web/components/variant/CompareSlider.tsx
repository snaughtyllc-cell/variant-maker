"use client";
import { useRef, useState, useCallback } from "react";
import { clipInset } from "@/lib/media";

export interface CompareSliderVideoRefs {
  beforeRef: React.RefObject<HTMLVideoElement | null>;
  afterRef: React.RefObject<HTMLVideoElement | null>;
}

interface CompareSliderProps {
  beforeSrc: string;
  afterSrc: string;
  /** Optional external refs — Task 9 uses these to wire into ScrubBar */
  videoRefs?: CompareSliderVideoRefs;
}

export function CompareSlider({ beforeSrc, afterSrc, videoRefs }: CompareSliderProps) {
  const [pct, setPct] = useState(54);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Internal refs — component works standalone without videoRefs
  const internalBeforeRef = useRef<HTMLVideoElement>(null);
  const internalAfterRef = useRef<HTMLVideoElement>(null);

  // The actual DOM refs are whichever were provided externally, else internal
  const beforeRef = videoRefs?.beforeRef ?? internalBeforeRef;
  const afterRef = videoRefs?.afterRef ?? internalAfterRef;

  const updatePct = useCallback((clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const raw = ((clientX - rect.left) / rect.width) * 100;
    setPct(Math.min(100, Math.max(0, raw)));
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    dragging.current = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    updatePct(e.clientX);
  }, [updatePct]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    updatePct(e.clientX);
  }, [updatePct]);

  const onPointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        aspectRatio: "9 / 16",
        borderRadius: 12,
        overflow: "hidden",
        border: "1px solid var(--color-line)",
        cursor: "ew-resize",
        userSelect: "none",
        touchAction: "none",
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      {/* AFTER (variant) — bottom layer, fills entire box */}
      <video
        ref={afterRef}
        src={afterSrc}
        muted
        playsInline
        preload="metadata"
        loop
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />

      {/* BEFORE (source) — top layer, clipped to reveal only left pct% */}
      <video
        ref={beforeRef}
        src={beforeSrc}
        muted
        playsInline
        preload="metadata"
        loop
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
          clipPath: clipInset(pct),
        }}
      />

      {/* Pill labels */}
      <span
        style={{
          position: "absolute",
          top: 8,
          left: 8,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.5px",
          textTransform: "uppercase",
          padding: "2px 7px",
          borderRadius: 6,
          color: "#fff",
          background: "#00000080",
          pointerEvents: "none",
        }}
      >
        SOURCE
      </span>
      <span
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.5px",
          textTransform: "uppercase",
          padding: "2px 7px",
          borderRadius: 6,
          color: "#fff",
          background: "#00000080",
          pointerEvents: "none",
        }}
      >
        VARIANT
      </span>

      {/* Vertical handle line + grip */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${pct}%`,
          width: 2,
          background: "#fff",
          transform: "translateX(-50%)",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 30,
            height: 30,
            borderRadius: "50%",
            background: "#fff",
            color: "#111",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            boxShadow: "0 2px 10px #000",
          }}
        >
          ⇄
        </div>
      </div>
    </div>
  );
}
