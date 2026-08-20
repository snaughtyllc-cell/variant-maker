"use client";
import { useState, useCallback } from "react";
import { DropZone } from "@/components/studio/DropZone";
import { FileList } from "@/components/studio/FileList";
import { DrivePickList } from "@/components/studio/DrivePickList";
import { DrivePickerModal, type DrivePick } from "@/components/studio/DrivePickerModal";
import { VariantStepper } from "@/components/studio/VariantStepper";
import { GenerateButton } from "@/components/studio/GenerateButton";
import { AdvancedPanel } from "@/components/studio/AdvancedPanel";
import { EngineWaitNote } from "@/components/studio/EngineWaitNote";
import { StudioQueue } from "@/components/studio/StudioQueueLive";
import { ProgressPanel } from "@/components/studio/ProgressPanel";
import { readDurations, tooLargeMessage, totalVariants } from "@/lib/files";
import { DEFAULT_PER_VIDEO, MAX_PER_VIDEO } from "@/lib/variantStepperCopy";
import { createJob, createJobFromDrive } from "@/lib/api";
import { useRun } from "@/lib/runStore";
import { studioProgressIdleClass, studioShellClass } from "@/lib/studioLayout";

export default function StudioPage() {
  const { start, jobId, complete } = useRun();
  const [files, setFiles] = useState<File[]>([]);
  const [durations, setDurations] = useState<number[]>([]);
  const [drivePicks, setDrivePicks] = useState<DrivePick[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [perVideo, setPerVideo] = useState(DEFAULT_PER_VIDEO);
  const [allowCreativeEscalate, setAllowCreativeEscalate] = useState(true);
  const [qualityMode, setQualityMode] = useState<"fast" | "hq">("fast");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sourceCount = files.length + drivePicks.length;
  const driveDestinationId = drivePicks[0]?.destinationId ?? null;

  const handleFiles = useCallback(async (incoming: File[]) => {
    const blocked = incoming.map(tooLargeMessage).find(Boolean);
    if (blocked) {
      setError(blocked);
      return;
    }
    setError(null);
    setFiles((prev) => {
      const combined = [...prev, ...incoming];
      readDurations(combined).then(setDurations);
      return combined;
    });
  }, []);

  function handleRemoveFile(index: number) {
    setFiles((prev) => {
      const next = prev.filter((_, i) => i !== index);
      readDurations(next).then(setDurations);
      return next;
    });
  }

  function handleRemoveDrivePick(index: number) {
    setDrivePicks((prev) => prev.filter((_, i) => i !== index));
  }

  function handleDriveConfirm(picks: DrivePick[]) {
    if (picks.length === 0) return;
    const destId = picks[0].destinationId;
    setDrivePicks((prev) => {
      if (prev.length === 0 || prev[0].destinationId !== destId) return picks;
      const byId = new Map(prev.map((p) => [p.id, p]));
      for (const p of picks) byId.set(p.id, p);
      return Array.from(byId.values());
    });
    setError(null);
  }

  async function handleGenerate() {
    if (busy || jobId || sourceCount === 0) return;
    if (files.length > 0 && drivePicks.length > 0) {
      setError("Use either phone files or Drive clips in one run — not both.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const resp =
        drivePicks.length > 0
          ? await createJobFromDrive({
              destinationId: drivePicks[0].destinationId,
              fileIds: drivePicks.map((p) => p.id),
              count: perVideo,
              qualityMode,
              allowCreativeEscalate,
            })
          : await createJob(files, perVideo, allowCreativeEscalate, qualityMode);
      start(resp, qualityMode);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Job failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={studioShellClass(!!jobId)}>
      <div className="studio-cockpit">
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

        <EngineWaitNote />
        <StudioQueue qualityMode={qualityMode} jobId={jobId} />

        <DropZone onFiles={handleFiles} />

        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          disabled={!!jobId}
          style={{
            marginTop: 10,
            width: "100%",
            fontSize: 12.5,
            fontWeight: 600,
            color: "var(--color-text)",
            background: "var(--color-panel2)",
            border: "1px solid var(--color-line)",
            padding: "10px 14px",
            borderRadius: 10,
            cursor: jobId ? "not-allowed" : "pointer",
            opacity: jobId ? 0.6 : 1,
          }}
        >
          From Google Drive
        </button>

        <FileList files={files} durations={durations} onRemove={handleRemoveFile} />
        <DrivePickList picks={drivePicks} onRemove={handleRemoveDrivePick} />

        <div className="studio-actions">
          <VariantStepper
            value={perVideo}
            onChange={setPerVideo}
            min={1}
            max={MAX_PER_VIDEO}
            fileCount={sourceCount}
            qualityMode={qualityMode}
          />
          <GenerateButton
            fileCount={sourceCount}
            perVideo={perVideo}
            onClick={handleGenerate}
            disabled={!!jobId}
            busy={busy}
            jobId={jobId}
            complete={complete}
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
          qualityMode={qualityMode}
          onQualityModeChange={setQualityMode}
          totalVariants={totalVariants(sourceCount, perVideo)}
        />
      </div>

      <div className={studioProgressIdleClass(!!jobId)}>
        <ProgressPanel />
      </div>

      {pickerOpen && (
        <DrivePickerModal
          existingDestinationId={driveDestinationId}
          onConfirm={handleDriveConfirm}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </main>
  );
}
