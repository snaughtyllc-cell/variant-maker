"use client";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { createDriveExport, previewCaptions } from "@/lib/api";
import { captionFilenamePreview } from "@/lib/captions";
import type { Destination, ExportJob, ExportVariantRef } from "@/lib/types";
import { ExportProgress } from "./ExportProgress";

interface SendToDriveModalProps {
  refs: ExportVariantRef[];
  destinations: Destination[];
  onClose: () => void;
}

export function SendToDriveModal({ refs, destinations, onClose }: SendToDriveModalProps) {
  const [destinationId, setDestinationId] = useState(destinations[0]?.id ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [captions, setCaptions] = useState<string[]>(() => refs.map(() => ""));
  const [fromBank, setFromBank] = useState(false);

  useEffect(() => {
    let cancelled = false;
    previewCaptions(refs.length)
      .then((out) => {
        if (cancelled) return;
        if (out.captions.length > 0) {
          setCaptions(out.captions);
          setFromBank(true);
        }
      })
      .catch(() => {/* keep blank captions; VA can type them */});
    return () => { cancelled = true; };
  }, [refs.length]);

  async function handleConfirm() {
    if (!destinationId || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createDriveExport(
        destinationId,
        refs.map((ref, i) => ({
          ...ref,
          caption: (captions[i] ?? "").trim() || undefined,
        })),
        fromBank,
      );
      setJob(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start export");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "#05050880",
            backdropFilter: "blur(1px)",
            zIndex: 60,
          }}
        />
        <Dialog.Content
          aria-describedby={undefined}
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 480,
            maxWidth: "calc(100vw - 32px)",
            maxHeight: "calc(100vh - 48px)",
            overflow: "auto",
            background: "linear-gradient(180deg, #0e0e15, #0b0b11)",
            border: "1px solid var(--color-line2)",
            borderRadius: 16,
            boxShadow: "0 30px 70px #000000aa",
            zIndex: 61,
            outline: "none",
            padding: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
            <Dialog.Title style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)", margin: 0 }}>
              Send to Drive
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              style={{
                marginLeft: "auto",
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "transparent",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-muted)",
                fontSize: 16,
                cursor: "pointer",
              }}
            >
              ✕
            </Dialog.Close>
          </div>

          {!job && (
            <>
              <div style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 14 }}>
                {refs.length} variant{refs.length !== 1 ? "s" : ""} selected. Filename is the
                Repurpose caption — edit before send.
              </div>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span style={{ fontSize: 12, color: "var(--color-muted)" }}>Destination</span>
                <select
                  value={destinationId}
                  onChange={(e) => setDestinationId(e.target.value)}
                  style={{
                    background: "var(--color-panel2)",
                    border: "1px solid var(--color-line)",
                    borderRadius: 9,
                    padding: "9px 12px",
                    fontSize: 13,
                    color: "var(--color-text)",
                    outline: "none",
                  }}
                >
                  {destinations.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>

              <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10, maxHeight: 280, overflow: "auto" }}>
                {refs.map((ref, i) => (
                  <label key={`${ref.source_id}:${ref.index}`} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <span style={{ fontSize: 11.5, color: "var(--color-muted)" }}>
                      v{String(ref.index).padStart(2, "0")} → {captionFilenamePreview(captions[i] ?? "", `v${String(ref.index).padStart(2, "0")}.mp4`)}
                    </span>
                    <textarea
                      value={captions[i] ?? ""}
                      onChange={(e) => {
                        const next = [...captions];
                        next[i] = e.target.value;
                        setCaptions(next);
                      }}
                      rows={2}
                      placeholder="Caption (Drive filename)"
                      style={{
                        background: "var(--color-panel2)",
                        border: "1px solid var(--color-line)",
                        borderRadius: 9,
                        padding: "8px 10px",
                        fontSize: 12.5,
                        color: "var(--color-text)",
                        outline: "none",
                        resize: "vertical",
                      }}
                    />
                  </label>
                ))}
              </div>

              {error && (
                <div style={{ fontSize: 12, color: "var(--color-red)", marginTop: 10 }}>{error}</div>
              )}

              <div style={{ display: "flex", gap: 8, marginTop: 18, justifyContent: "flex-end" }}>
                <button
                  onClick={onClose}
                  style={{
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: "var(--color-text)",
                    background: "var(--color-panel2)",
                    border: "1px solid var(--color-line)",
                    padding: "8px 14px",
                    borderRadius: 9,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={submitting || !destinationId}
                  style={{
                    fontSize: 12.5,
                    fontWeight: 700,
                    color: "#fff",
                    background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
                    border: "none",
                    padding: "8px 16px",
                    borderRadius: 9,
                    cursor: submitting || !destinationId ? "not-allowed" : "pointer",
                    opacity: submitting || !destinationId ? 0.7 : 1,
                  }}
                >
                  {submitting ? "Starting…" : "Confirm"}
                </button>
              </div>
            </>
          )}

          {job && <ExportProgress exportId={job.export_id} initial={job} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
