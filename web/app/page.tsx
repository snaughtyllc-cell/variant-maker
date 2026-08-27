"use client";
import { useState, useCallback } from "react";
import { DropZone } from "@/components/studio/DropZone";
import { FileList } from "@/components/studio/FileList";
import { DrivePickList } from "@/components/studio/DrivePickList";
import { DrivePickerModal, type DrivePick } from "@/components/studio/DrivePickerModal";
import { VariantStepper } from "@/components/studio/VariantStepper";
import { GenerateButton } from "@/components/studio/GenerateButton";
import { AdvancedPanel } from "@/components/studio/AdvancedPanel";
import { StudioQueue } from "@/components/studio/StudioQueueLive";
import { ProgressPanel } from "@/components/studio/ProgressPanel";
import { readDurations, tooLargeMessage, totalVariants } from "@/lib/files";
import { DEFAULT_PER_VIDEO, MAX_PER_VIDEO } from "@/lib/variantStepperCopy";
import { captionToggleHint, captionToggleLabel } from "@/lib/prepareCopy";
import { createJob, createJobFromDrive } from "@/lib/api";
import { useRun } from "@/lib/runStore";
import { useAuthMe } from "@/lib/useAuthMe";
import { isAgencyExperience } from "@/lib/experience";
import { studioProgressIdleClass, studioShellClass } from "@/lib/studioLayout";

export default function StudioPage() {
  const { start, beginPrepare, clear, jobId, complete } = useRun();
  const { data: me } = useAuthMe();
  const agency = isAgencyExperience(me);
  const [files, setFiles] = useState<File[]>([]);
  const [durations, setDurations] = useState<number[]>([]);
  const [drivePicks, setDrivePicks] = useState<DrivePick[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [perVideo, setPerVideo] = useState(DEFAULT_PER_VIDEO);
  const [allowCreativeEscalate, setAllowCreativeEscalate] = useState(true);
  const [qualityMode, setQualityMode] = useState<"fast" | "hq">("fast");
  const [generateCaptions, setGenerateCaptions] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sourceCount = files.length + drivePicks.length;
  const driveDestinationId = drivePicks[0]?.destinationId ?? null;
  const jobLocked = Boolean(jobId && !complete);

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
    if (busy || sourceCount === 0) return;
    if (jobId && !complete) return;
    if (files.length > 0 && drivePicks.length > 0) {
      setError("Use either phone files or Drive clips in one run — not both.");
      return;
    }
    setError(null);
    const names = files.length > 0
      ? files.map((f) => f.name)
      : drivePicks.map((p) => p.name);
    beginPrepare(names.map((filename, i) => ({
      source_id: `prep-${i}`,
      filename,
      requested: perVideo,
    })));
    setBusy(true);
    try {
      const resp =
        drivePicks.length > 0
          ? await createJobFromDrive({
              destinationId: drivePicks[0].destinationId,
              fileIds: drivePicks.map((p) => p.id),
              count: perVideo,
              qualityMode: "fast",
              allowCreativeEscalate,
              generateCaptions,
            })
          : await createJob(files, perVideo, allowCreativeEscalate, "fast", generateCaptions);
      start(resp, "fast");
    } catch (e) {
      clear();
      setError(e instanceof Error ? e.message : "Job failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={studioShellClass(!!jobId)}>
      <div className="studio-cockpit">
        <div className="studio-cockpit__scroll">
          <div className="studio-cockpit__inner">
            <header className="studio-intro">
              <p>Studio</p>
              <h1>Build a pack</h1>
              <span>Pick clips, set variants, watch the queue on the right.</span>
            </header>

            <StudioQueue qualityMode={qualityMode} jobId={jobId} />

            <section className="studio-section">
              <div className="studio-section__head">
                <p className="studio-eyebrow">01 · Source</p>
                <span className="studio-section__meta">
                  {sourceCount > 0 ? `${sourceCount} clip${sourceCount !== 1 ? "s" : ""}` : "No clips yet"}
                </span>
              </div>

              <DropZone onFiles={handleFiles} />

              <div className="studio-source-actions">
                <button
                  type="button"
                  onClick={() => setPickerOpen(true)}
                  disabled={jobLocked}
                  className="studio-drive-picker"
                >
                  <span className="material-symbols-rounded" style={{ fontSize: 18 }}>cloud</span>
                  From Drive
                </button>
                <span className="studio-source-hint">MP4 / MOV · up to 1 GB each</span>
              </div>

              <div className="studio-source-row">
                <FileList files={files} durations={durations} onRemove={handleRemoveFile} />
                <DrivePickList picks={drivePicks} onRemove={handleRemoveDrivePick} />
              </div>
            </section>

            <hr className="studio-divider" />

            <section className="studio-section">
              <p className="studio-eyebrow">02 · Variants per clip</p>
              <VariantStepper
                value={perVideo}
                onChange={setPerVideo}
                min={1}
                max={MAX_PER_VIDEO}
                fileCount={sourceCount}
                qualityMode={qualityMode}
              />
            </section>

            <hr className="studio-divider" />

            <section className="studio-section">
              <p className="studio-eyebrow">03 · Options</p>
              <div className="studio-options">
                <label className="studio-option-row studio-caption-toggle">
                  <div>
                    <div className="studio-option-row__label">{captionToggleLabel()}</div>
                    <div className="studio-option-row__hint">{captionToggleHint()}</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={generateCaptions}
                    onChange={(e) => setGenerateCaptions(e.target.checked)}
                  />
                  <span className="studio-switch" data-on={generateCaptions} aria-hidden="true">
                    <span className="studio-switch__thumb" />
                  </span>
                </label>

                {agency && (
                  <AdvancedPanel
                    allowCreativeEscalate={allowCreativeEscalate}
                    onAllowCreativeEscalateChange={setAllowCreativeEscalate}
                    qualityMode={qualityMode}
                    onQualityModeChange={setQualityMode}
                    totalVariants={totalVariants(sourceCount, perVideo)}
                  />
                )}
              </div>
            </section>

            {error && (
              <div className="vf-alert vf-alert--error" style={{ margin: 0 }}>
                {error}
              </div>
            )}

            <div className="studio-cockpit__spacer" />
          </div>
        </div>

        <div className="studio-generate-bar">
          <div className="studio-generate-bar__inner">
            <GenerateButton
              fileCount={sourceCount}
              perVideo={perVideo}
              onClick={handleGenerate}
              disabled={jobLocked}
              busy={busy}
              jobId={jobId}
              complete={complete}
            />
          </div>
        </div>
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
