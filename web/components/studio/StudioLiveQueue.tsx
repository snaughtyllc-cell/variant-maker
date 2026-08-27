"use client";
import { useState } from "react";
import Link from "next/link";
import { cancelJob } from "@/lib/api";
import { useQueue } from "@/lib/useQueue";
import { useRun } from "@/lib/runStore";
import { displayClipName } from "@/lib/queue";

interface QueueRow {
  key: string;
  name: string;
  label: string;
  pct: number;
  cancelId?: string;
}

interface FinishedTile {
  key: string;
  v: string;
  pct: string;
  color: string;
}

/**
 * Persistent dark LIVE QUEUE rail (mock "Studio · web", right column).
 * Wired to the real shared queue (`useQueue`) plus this browser's own run
 * (`useRun` → live SSE progress + finished tiles). No fabricated data:
 * rows are running packs, tiles are variants this session actually finished.
 */
export function StudioLiveQueue() {
  const { data: queue, mutate } = useQueue();
  const { jobId, progress, complete } = useRun();
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  const runSources = Object.values(progress.bySource);
  const activeRun = Boolean(jobId) && !complete;
  const localInQueue = jobId ? queue.jobs.some((j) => j.job_id === jobId) : false;
  const localDelivered = runSources.reduce((sum, s) => sum + s.delivered, 0);

  const running = queue.running + (activeRun && !localInQueue ? 1 : 0);
  const done =
    queue.jobs.reduce((sum, j) => sum + j.delivered, 0) + (localInQueue ? 0 : localDelivered);

  // Live rows for this browser's own run before the shared queue registers it,
  // then the queue's authoritative rows (which include everyone's packs).
  const runRows: QueueRow[] =
    activeRun && !localInQueue
      ? runSources.map((s) => ({
          key: `run-${s.source_id}`,
          name: displayClipName(s.filename),
          label: `${s.delivered}/${s.requested}`,
          pct: s.requested > 0 ? Math.min(100, Math.round((s.done / s.requested) * 100)) : 0,
        }))
      : [];

  const queueRows: QueueRow[] = queue.jobs.map((j) => {
    const first = displayClipName(j.filenames[0] ?? "clip");
    const extra = j.filenames.length > 1 ? ` +${j.filenames.length - 1}` : "";
    return {
      key: `job-${j.job_id}`,
      name: `${first}${extra}`,
      label: `${j.delivered}/${j.requested}`,
      pct: j.requested > 0 ? Math.min(100, Math.round((j.delivered / j.requested) * 100)) : 0,
      cancelId: j.state === "running" ? j.job_id : undefined,
    };
  });

  const rows = [...runRows, ...queueRows];

  const finished: FinishedTile[] = runSources
    .flatMap((s) => s.variants)
    .filter(
      (v) => v.status === "ok" || v.status === "best_effort" || v.status === "uniqueness_fail",
    )
    .slice(-9)
    .reverse()
    .map((v) => {
      const pctNum = v.uniqueness != null ? Math.round(v.uniqueness * 100) : null;
      const miss = v.status === "uniqueness_fail";
      return {
        key: `${v.filename}-${v.index}`,
        v: `v${String(v.index).padStart(2, "0")}`,
        pct: pctNum != null ? `${pctNum}%` : "·",
        color: miss ? "var(--color-red)" : "#7ee0e6",
      };
    });

  async function handleCancel(id: string) {
    if (cancellingId) return;
    setCancellingId(id);
    try {
      await cancelJob(id);
      await mutate();
    } catch {
      // Poll drops the row once the job actually closes.
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <aside className="studio-live" aria-label="Live queue">
      <div className="studio-live__head">
        <span className="studio-live__title">LIVE QUEUE</span>
        <span className="studio-live__count">
          {running} running · {done} done
        </span>
      </div>

      {progress.failed && !complete && (
        <p className="studio-live__failed">{progress.failed}</p>
      )}

      {rows.length > 0 ? (
        <div className="studio-live__rows">
          {rows.map((row) => (
            <div className="studio-live-row" key={row.key}>
              <div className="studio-live-row__thumb" />
              <div className="studio-live-row__main">
                <div className="studio-live-row__top">
                  <span className="studio-live-row__name">{row.name}</span>
                  <span className="studio-live-row__pct">{row.label}</span>
                </div>
                <div className="studio-live-row__bar">
                  <div className="studio-live-row__fill" style={{ width: `${row.pct}%` }} />
                </div>
              </div>
              {row.cancelId && (
                <button
                  type="button"
                  className="studio-live-row__cancel"
                  onClick={() => handleCancel(row.cancelId!)}
                  disabled={cancellingId === row.cancelId}
                  aria-label="Cancel pack"
                  title="Cancel pack"
                >
                  <span className="material-symbols-rounded" style={{ fontSize: 16 }}>
                    {cancellingId === row.cancelId ? "hourglass_empty" : "close"}
                  </span>
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="studio-live__empty">
          Queue is clear. Generate a pack and it renders here live.
        </p>
      )}

      <div className="studio-live__divider" />
      <div className="studio-live__title studio-live__title--sub">JUST FINISHED</div>

      {finished.length > 0 ? (
        <div className="studio-live__grid">
          {finished.map((tile) => (
            <div className="studio-live-tile" key={tile.key}>
              <span className="studio-live-tile__v">{tile.v}</span>
              <span className="studio-live-tile__pct" style={{ color: tile.color }}>
                {tile.pct}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="studio-live__empty studio-live__empty--sub">
          Finished variants land here, then Open Gallery.
        </p>
      )}

      <div className="studio-live__spacer" />

      <Link className="studio-live__gallery" href="/gallery">
        Open Gallery
        <span className="material-symbols-rounded" style={{ fontSize: 17 }}>arrow_forward</span>
      </Link>
    </aside>
  );
}
