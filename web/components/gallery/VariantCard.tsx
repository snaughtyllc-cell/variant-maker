"use client";
import { VideoThumb } from "../common/VideoThumb";
import { VariantOut } from "@/lib/types";

interface VariantCardProps {
  variant: VariantOut;
  sourceId: string;
  onOpen: () => void;
}

export function VariantCard({ variant, onOpen }: VariantCardProps) {
  const vmaf = Math.round(variant.quality.vmaf);
  const spatialOk = variant.quality.spatial_ok === true;

  const badge = (
    <div
      style={{
        position: "absolute",
        inset: "auto 0 0 0",
        padding: "5px 6px",
        display: "flex",
        alignItems: "center",
        gap: 4,
        background: "linear-gradient(transparent, #000000bb)",
      }}
    >
      {/* VMAF badge */}
      <span
        style={{
          fontSize: 9,
          fontWeight: 800,
          padding: "1px 5px",
          borderRadius: 5,
          background: "#0b3d1f",
          color: "#7bf2a8",
          border: "1px solid #134d28",
          lineHeight: 1.4,
        }}
      >
        {vmaf}
      </span>
      {/* Spatial tick — ONLY when spatial_ok === true */}
      {spatialOk && (
        <span
          style={{
            marginLeft: "auto",
            fontSize: 9,
            color: "#7bf2a8",
            fontWeight: 700,
          }}
        >
          ✓ spatial
        </span>
      )}
    </div>
  );

  return (
    <div
      onClick={onOpen}
      style={{
        aspectRatio: "9 / 16",
        borderRadius: 9,
        position: "relative",
        overflow: "hidden",
        cursor: "pointer",
        border: "1px solid var(--color-line)",
        transition: "transform 0.1s ease, box-shadow 0.1s ease, border-color 0.1s ease",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 8px 20px #00000055";
        (e.currentTarget as HTMLDivElement).style.borderColor = "#2f2a52";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = "";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "";
        (e.currentTarget as HTMLDivElement).style.borderColor = "var(--color-line)";
      }}
    >
      {/* Index label */}
      <span
        style={{
          position: "absolute",
          top: 5,
          left: 6,
          fontSize: 9,
          color: "#fff",
          opacity: 0.8,
          fontWeight: 700,
          textShadow: "0 1px 3px #000",
          zIndex: 2,
          pointerEvents: "none",
        }}
      >
        v{String(variant.index + 1).padStart(2, "0")}
      </span>
      <VideoThumb src={variant.file_url} className="absolute inset-0 w-full h-full" />
      {/* Overlay with badges */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {badge}
      </div>
    </div>
  );
}
