import { captionEmptyCopy, captionPreviewLabel } from "@/lib/prepareCopy";

export function CaptionBlock({ caption }: { caption?: string | null }) {
  const text = (caption || "").trim();

  return (
    <div style={{ marginTop: 16 }}>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.7px",
          color: "var(--color-muted2)",
          fontWeight: 700,
          margin: "0 0 10px",
        }}
      >
        {captionPreviewLabel()}
      </div>
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          color: text ? "var(--color-text)" : "var(--color-muted)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {text || captionEmptyCopy()}
      </div>
    </div>
  );
}
