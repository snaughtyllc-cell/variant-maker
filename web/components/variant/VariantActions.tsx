"use client";
import { useState } from "react";
import { PlatformResult, VariantOut } from "@/lib/types";
import { regenerate, setPlatformResult } from "@/lib/api";
import { PostLinkField } from "./PostLinkField";

interface VariantActionsProps {
  sourceId: string;
  variant: VariantOut;
  onRegenerate: () => void;
}

export function VariantActions({ sourceId, variant, onRegenerate }: VariantActionsProps) {
  const [busy, setBusy] = useState(false);
  const [resultBusy, setResultBusy] = useState<PlatformResult | null>(null);

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

  async function handleSetResult(result: PlatformResult) {
    if (resultBusy) return;
    setResultBusy(result);
    try {
      await setPlatformResult(sourceId, variant.index, result);
      onRegenerate();
    } catch (e) {
      console.error("Set platform result failed", e);
    } finally {
      setResultBusy(null);
    }
  }

  const currentResult = variant.platform_result ?? "unknown";
  const isDuplicate = currentResult === "duplicate_reject";

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
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span>Actions</span>
        {isDuplicate && (
          <span
            data-testid="platform-result-badge"
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "2px 8px",
              borderRadius: 999,
              textTransform: "none",
              letterSpacing: 0,
              color: "#8e6119",
              background: "#fff8eb",
              border: "1px solid #efdfbd",
            }}
          >
            ⚠ Duplicate rejected
          </span>
        )}
      </div>

      <PostLinkField sourceId={sourceId} variant={variant} onSaved={onRegenerate} />

      <button
        onClick={() => handleSetResult("duplicate_reject")}
        disabled={!!resultBusy}
        style={{
          display: "flex",
          width: "100%",
          alignItems: "center",
          justifyContent: "center",
          gap: 7,
          fontSize: 12.5,
          fontWeight: 700,
          padding: "10px",
          marginBottom: 6,
          borderRadius: 10,
          background: isDuplicate ? "#fff8eb" : "#f3f8f9",
          border: `1px solid ${isDuplicate ? "#efdfbd" : "var(--color-line)"}`,
          color: isDuplicate ? "#8e6119" : "var(--color-text)",
          cursor: resultBusy ? "not-allowed" : "pointer",
          opacity: resultBusy && resultBusy !== "duplicate_reject" ? 0.6 : 1,
        }}
      >
        ⚠ {resultBusy === "duplicate_reject" ? "Saving…" : "Duplicate rejected"}
      </button>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-muted)",
          lineHeight: 1.45,
          marginBottom: 9,
        }}
      >
        Unlabeled = pass. Only mark duplicate when the platform took it down.
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 9,
        }}
      >
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
            background: "var(--ink)",
            border: "none",
            color: "#f7fbfb",
            boxShadow: "none",
            textDecoration: "none",
            cursor: "pointer",
          }}
        >
          ⬇ Download variant
        </a>

        <button
          onClick={handleRegenerate}
          disabled={busy}
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
            background: "#f3f8f9",
            border: "1px solid var(--color-line)",
            color: busy ? "var(--color-muted)" : "var(--color-text)",
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.7 : 1,
          }}
        >
          ↻ {busy ? "Regenerating…" : "Regenerate this one"}
        </button>
      </div>
    </div>
  );
}
