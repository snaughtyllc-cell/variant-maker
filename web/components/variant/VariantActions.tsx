"use client";
import { useState } from "react";
import { VariantOut } from "@/lib/types";
import { regenerate } from "@/lib/api";

interface VariantActionsProps {
  sourceId: string;
  variant: VariantOut;
  onRegenerate: () => void;
}

export function VariantActions({ sourceId, variant, onRegenerate }: VariantActionsProps) {
  const [busy, setBusy] = useState(false);
  const [manifestOpen, setManifestOpen] = useState(false);

  async function handleRegenerate() {
    if (busy) return;
    setBusy(true);
    try {
      await regenerate(sourceId, 1);
      onRegenerate();
    } catch (e) {
      console.error("Regenerate failed", e);
    } finally {
      setBusy(false);
    }
  }

  const manifestJson = JSON.stringify(
    {
      index: variant.index,
      filename: variant.filename,
      file_url: variant.file_url,
      status: variant.status,
      quality: variant.quality,
    },
    null,
    2,
  );

  return (
    <div style={{ marginTop: 18 }}>
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
        Actions
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 9,
        }}
      >
        {/* Download — spans full width, primary CTA */}
        <a
          href={variant.file_url}
          download={variant.filename}
          style={{
            gridColumn: "span 2",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "11px",
            borderRadius: 10,
            backgroundImage: "var(--background-image-cta)",
            border: "none",
            color: "#fff",
            boxShadow: "0 4px 14px #ff4d8d33",
            textDecoration: "none",
            cursor: "pointer",
          }}
        >
          ⬇ Download variant
        </a>

        {/* Regenerate this one */}
        <button
          onClick={handleRegenerate}
          disabled={busy}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "11px",
            borderRadius: 10,
            background: "#16161f",
            border: "1px solid var(--color-line)",
            color: busy ? "var(--color-muted)" : "var(--color-text)",
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.7 : 1,
          }}
        >
          ↻ {busy ? "Regenerating…" : "Regenerate this one"}
        </button>

        {/* View manifest entry */}
        <button
          onClick={() => setManifestOpen((o) => !o)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "11px",
            borderRadius: 10,
            background: "#16161f",
            border: "1px solid var(--color-line)",
            color: "var(--color-text)",
            cursor: "pointer",
          }}
        >
          {"{ }"} View manifest entry
        </button>
      </div>

      {/* Manifest disclosure */}
      {manifestOpen && (
        <div
          style={{
            marginTop: 10,
            background: "#0c0c14",
            border: "1px solid var(--color-line)",
            borderRadius: 10,
            padding: "12px 14px",
            overflow: "auto",
          }}
        >
          <pre
            style={{
              margin: 0,
              fontSize: 11,
              color: "var(--color-muted)",
              fontFamily: "'SF Mono', ui-monospace, Menlo, monospace",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
            }}
          >
            {manifestJson}
          </pre>
        </div>
      )}
    </div>
  );
}
