"use client";
import { useState, useCallback } from "react";
import { DropZone } from "@/components/studio/DropZone";
import { FileList } from "@/components/studio/FileList";
import { VariantStepper } from "@/components/studio/VariantStepper";
import { GenerateButton } from "@/components/studio/GenerateButton";
import { AdvancedPanel } from "@/components/studio/AdvancedPanel";
import { ProgressPanel } from "@/components/studio/ProgressPanel";
import { readDurations } from "@/lib/files";
import { createJob } from "@/lib/api";
import { useRun } from "@/lib/runStore";

export default function StudioPage() {
  const { start, jobId, complete } = useRun();
  const [files, setFiles] = useState<File[]>([]);
  const [durations, setDurations] = useState<number[]>([]);
  const [perVideo, setPerVideo] = useState(5);
  const [allowCreativeEscalate, setAllowCreativeEscalate] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A run is "active" when there's a jobId and it's not yet complete
  const runActive = !!jobId && !complete;

  const handleFiles = useCallback(async (incoming: File[]) => {
    setFiles((prev) => {
      const combined = [...prev, ...incoming];
      // fire-and-forget duration reads for the new batch
      readDurations(combined).then(setDurations);
      return combined;
    });
  }, []);

  function handleRemove(index: number) {
    setFiles((prev) => {
      const next = prev.filter((_, i) => i !== index);
      readDurations(next).then(setDurations);
      return next;
    });
  }

  async function handleGenerate() {
    if (busy || runActive || files.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const resp = await createJob(files, perVideo, allowCreativeEscalate);
      start(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Job failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        display: "grid",
        gridTemplateColumns: "0.95fr 1.05fr",
        minHeight: "calc(100vh - 49px)", // subtract top nav height
        background: "var(--color-bg)",
      }}
    >
      {/* LEFT — cockpit */}
      <div
        style={{
          padding: "22px",
          borderRight: "1px solid var(--color-line)",
        }}
      >
        <p
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: ".7px",
            color: "var(--color-muted2)",
            margin: "0 0 8px",
            fontWeight: 700,
          }}
        >
          1 · Source videos
        </p>

        <DropZone onFiles={handleFiles} />

        <FileList files={files} durations={durations} onRemove={handleRemove} />

        <div style={{ display: "flex", gap: 12, alignItems: "stretch", marginTop: 20 }}>
          <VariantStepper
            value={perVideo}
            onChange={setPerVideo}
            min={1}
            fileCount={files.length}
          />
          <GenerateButton
            fileCount={files.length}
            perVideo={perVideo}
            onClick={handleGenerate}
            disabled={runActive}
            busy={busy}
          />
        </div>

        {error && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "#2a0e0e",
              border: "1px solid #5a1a1a",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--color-red)",
            }}
          >
            {error}
          </div>
        )}

        <AdvancedPanel
          allowCreativeEscalate={allowCreativeEscalate}
          onAllowCreativeEscalateChange={setAllowCreativeEscalate}
        />
      </div>

      {/* RIGHT — live progress (Task 6) */}
      <div
        style={{
          padding: "18px 20px",
          background: "#0c0c11",
          display: "flex",
          flexDirection: "column",
          minHeight: 0,
        }}
      >
        <ProgressPanel />
      </div>
    </main>
  );
}
