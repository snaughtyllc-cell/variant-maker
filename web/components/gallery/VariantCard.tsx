"use client";
import { VideoThumb } from "../common/VideoThumb";
import { VariantOut } from "@/lib/types";

interface VariantCardProps {
  variant: VariantOut;
  sourceId: string;
  onOpen: () => void;
  selected: boolean;
  onToggle: () => void;
}

export function VariantCard({ variant, onOpen, selected, onToggle }: VariantCardProps) {
  const vmaf = variant.quality?.vmaf != null ? Math.round(variant.quality.vmaf) : null;
  const spatialOk = variant.quality?.spatial_ok === true;
  const uniquenessPct = variant.uniqueness != null ? Math.round(variant.uniqueness * 100) : null;
  const uniquenessOk = variant.uniqueness_status === "ok";

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
          background: vmaf != null ? "#0b3d1f" : "#1e1e2a",
          color: vmaf != null ? "#7bf2a8" : "#888",
          border: vmaf != null ? "1px solid #134d28" : "1px solid #333",
          lineHeight: 1.4,
        }}
      >
        {vmaf ?? "–"}
      </span>
      {/* Uniqueness badge */}
      {uniquenessPct != null && (
        <span
          style={{
            fontSize: 9,
            fontWeight: 800,
            padding: "1px 5px",
            borderRadius: 5,
            background: uniquenessOk ? "#072830" : "#3d2200",
            color: uniquenessOk ? "#22d3ee" : "#f59e0b",
            border: `1px solid ${uniquenessOk ? "#0c3d47" : "#4d2e00"}`,
            lineHeight: 1.4,
          }}
        >
          {uniquenessPct}%
        </span>
      )}
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

  const topBadges = (
    <div
      style={{
        position: "absolute",
        top: 5,
        right: 6,
        display: "flex",
        gap: 3,
        zIndex: 2,
      }}
    >
      {variant.escalated && (
        <span
          style={{
            fontSize: 8,
            fontWeight: 800,
            padding: "1px 5px",
            borderRadius: 5,
            background: "#1e1740",
            color: "#c7b8ff",
            border: "1px solid #362a68",
            textShadow: "0 1px 2px #000",
          }}
        >
          ⚡
        </span>
      )}
      {variant.platform_result === "passed" && (
        <span
          style={{
            fontSize: 8,
            fontWeight: 800,
            padding: "1px 5px",
            borderRadius: 5,
            background: "#0b3d1f",
            color: "#7bf2a8",
            border: "1px solid #134d28",
          }}
        >
          ✓
        </span>
      )}
      {variant.platform_result === "duplicate_reject" && (
        <span
          style={{
            fontSize: 8,
            fontWeight: 800,
            padding: "1px 5px",
            borderRadius: 5,
            background: "#2c2210",
            color: "#ffd08a",
            border: "1px solid #5a4416",
          }}
        >
          ⚠
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
        border: selected ? "1px solid #7c5cff" : "1px solid var(--color-line)",
        boxShadow: selected ? "0 0 0 2px #7c5cff44" : undefined,
        transition: "transform 0.1s ease, box-shadow 0.1s ease, border-color 0.1s ease",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 8px 20px #00000055";
        (e.currentTarget as HTMLDivElement).style.borderColor = "#2f2a52";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.transform = "";
        (e.currentTarget as HTMLDivElement).style.boxShadow = selected ? "0 0 0 2px #7c5cff44" : "";
        (e.currentTarget as HTMLDivElement).style.borderColor = selected ? "#7c5cff" : "var(--color-line)";
      }}
    >
      {/* Selection checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        aria-label={`Select v${String(variant.index).padStart(2, "0")}`}
        style={{
          position: "absolute",
          top: 5,
          left: 5,
          width: 13,
          height: 13,
          zIndex: 3,
          cursor: "pointer",
          accentColor: "#7c5cff",
        }}
      />

      {/* Index label */}
      <span
        style={{
          position: "absolute",
          top: 5,
          left: 22,
          fontSize: 9,
          color: "#fff",
          opacity: 0.8,
          fontWeight: 700,
          textShadow: "0 1px 3px #000",
          zIndex: 2,
          pointerEvents: "none",
        }}
      >
        v{String(variant.index).padStart(2, "0")}
      </span>
      <VideoThumb src={variant.file_url} className="absolute inset-0 w-full h-full" />
      {/* Overlay with badges */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {topBadges}
        {badge}
      </div>
    </div>
  );
}
