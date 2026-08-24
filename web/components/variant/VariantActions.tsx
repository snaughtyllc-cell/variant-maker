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
  const [manifestOpen, setManifestOpen] = useState(false);
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

  const manifestJson = JSON.stringify(
    {
      index: variant.index,
      filename: variant.filename,
      file_url: variant.file_url,
      status: variant.status,
      quality: variant.quality,
      uniqueness: variant.uniqueness,
      uniqueness_status: variant.uniqueness_status,
      escalated: variant.escalated,
      platform_result: variant.platform_result,
      post_url: variant.post_url,
    },
    null,
    2,
  );

  const currentResult = variant.platform_result ?? "unknown";
  const resultBadge =
    currentResult === "passed"
      ? { text: "✓ Passed upload", color: "#247955", background: "#e9f8f0", border: "#c6e8d7" }
      : currentResult === "flagged"
        ? { text: "⚑ Flagged", color: "#a33f3d", background: "#fff3f1", border: "#efc5c0" }
        : { text: "⚠ Duplicate rejected", color: "#8e6119", background: "#fff8eb", border: "#efdfbd" };

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
        {currentResult !== "unknown" && (
          <span
            data-testid="platform-result-badge"
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "2px 8px",
              borderRadius: 999,
              textTransform: "none",
              letterSpacing: 0,
              color: resultBadge.color,
              background: resultBadge.background,
              border: `1px solid ${resultBadge.border}`,
            }}
          >
            {resultBadge.text}
          </span>
        )}
      </div>

      {/* VA-pasted live permalink — Studio does not post */}
      <PostLinkField sourceId={sourceId} variant={variant} onSaved={onRegenerate} />

      {/* Platform outcome — records what the real platform did with this upload */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 9,
          marginBottom: 6,
        }}
      >
        <button
          onClick={() => handleSetResult("passed")}
          disabled={!!resultBusy}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "10px",
            borderRadius: 10,
            background: currentResult === "passed" ? "#e9f8f0" : "#f3f8f9",
            border: `1px solid ${currentResult === "passed" ? "#c6e8d7" : "var(--color-line)"}`,
            color: currentResult === "passed" ? "#247955" : "var(--color-text)",
            cursor: resultBusy ? "not-allowed" : "pointer",
            opacity: resultBusy && resultBusy !== "passed" ? 0.6 : 1,
          }}
        >
          ✓ {resultBusy === "passed" ? "Saving…" : "Passed upload"}
        </button>
        <button
          onClick={() => handleSetResult("duplicate_reject")}
          disabled={!!resultBusy}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "10px",
            borderRadius: 10,
            background: currentResult === "duplicate_reject" ? "#fff8eb" : "#f3f8f9",
            border: `1px solid ${currentResult === "duplicate_reject" ? "#efdfbd" : "var(--color-line)"}`,
            color: currentResult === "duplicate_reject" ? "#8e6119" : "var(--color-text)",
            cursor: resultBusy ? "not-allowed" : "pointer",
            opacity: resultBusy && resultBusy !== "duplicate_reject" ? 0.6 : 1,
          }}
        >
          ⚠ {resultBusy === "duplicate_reject" ? "Saving…" : "Duplicate rejected"}
        </button>
        <button
          onClick={() => handleSetResult("flagged")}
          disabled={!!resultBusy}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 7,
            fontSize: 12.5,
            fontWeight: 700,
            padding: "10px",
            borderRadius: 10,
            background: currentResult === "flagged" ? "#fff3f1" : "#f3f8f9",
            border: `1px solid ${currentResult === "flagged" ? "#efc5c0" : "var(--color-line)"}`,
            color: currentResult === "flagged" ? "#a33f3d" : "var(--color-text)",
            cursor: resultBusy ? "not-allowed" : "pointer",
            opacity: resultBusy && resultBusy !== "flagged" ? 0.6 : 1,
          }}
        >
          ⚑ {resultBusy === "flagged" ? "Saving…" : "Flagged"}
        </button>
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-muted)",
          lineHeight: 1.45,
          marginBottom: 9,
        }}
      >
        Unlabeled = pass. Only mark duplicate or flagged when the platform took it down.
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
            background: "#f3f8f9",
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
            background: "#f3f8f9",
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
