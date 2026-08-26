import { captionSnippet } from "@/lib/prepareCopy";

export function CaptionSnippet({ caption }: { caption?: string | null }) {
  const text = captionSnippet(caption);
  if (!text) return null;

  return (
    <p
      style={{
        margin: 0,
        padding: "7px 8px 8px",
        fontSize: 11,
        lineHeight: 1.4,
        color: "var(--color-muted)",
        background: "var(--color-panel)",
      }}
    >
      {text}
    </p>
  );
}
