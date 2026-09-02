import { captionEmptyCopy, captionPreviewLabel } from "@/lib/prepareCopy";

export function CaptionBlock({ caption }: { caption?: string | null }) {
  const text = (caption || "").trim();

  return (
    <div style={{ marginTop: 18 }}>
      <div
        style={{
          fontFamily: "var(--font-space-grotesk), monospace",
          fontSize: 10.5,
          fontWeight: 600,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-violet)",
          margin: "0 0 10px",
        }}
      >
        {captionPreviewLabel()}
      </div>
      <div
        style={{
          fontSize: 15,
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
