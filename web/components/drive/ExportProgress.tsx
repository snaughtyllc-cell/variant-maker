"use client";
import { useEffect, useState } from "react";
import { getDriveExport, retryDriveExport } from "@/lib/api";
import { exportProgressLabel } from "@/lib/drive";
import type { ExportJob } from "@/lib/types";

const TERMINAL_STATES = new Set(["succeeded", "partial", "failed"]);
const POLL_MS = 500;

interface ExportProgressProps {
  exportId: string;
  initial: ExportJob;
}

export function ExportProgress({ exportId, initial }: ExportProgressProps) {
  const [job, setJob] = useState<ExportJob>(initial);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  // Poll while the job is running; re-armed whenever job.state flips (e.g. after retry).
  useEffect(() => {
    if (TERMINAL_STATES.has(job.state)) return;
    let cancelled = false;
    const id = setInterval(async () => {
      try {
        const next = await getDriveExport(exportId);
        if (!cancelled) setJob(next);
      } catch (e) {
        console.error("Failed to poll Drive export", e);
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [exportId, job.state]);

  async function handleRetry() {
    if (retrying) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const next = await retryDriveExport(exportId);
      setJob(next);
    } catch (e) {
      setRetryError(e instanceof Error ? e.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  }

  const { done, total, current } = exportProgressLabel(job);
  const isTerminal = TERMINAL_STATES.has(job.state);
  const failedFiles = job.files.filter((f) => f.status === "failed");
  const succeededCount = job.files.filter((f) => f.status === "succeeded").length;

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 8 }}>
        {done} / {total} files
        {!isTerminal && current && ` · uploading ${current}`}
      </div>

      <div
        style={{
          height: 6,
          borderRadius: 999,
          background: "#1c1c26",
          overflow: "hidden",
          marginBottom: 12,
        }}
      >
        <div
          style={{
            height: "100%",
            width: total > 0 ? `${(done / total) * 100}%` : "0%",
            background:
              job.state === "failed"
                ? "var(--color-red)"
                : "linear-gradient(135deg, #7c5cff, #ff4d8d)",
            transition: "width 0.2s ease",
          }}
        />
      </div>

      {isTerminal && (
        <div
          style={{
            fontSize: 13,
            fontWeight: 700,
            marginBottom: failedFiles.length > 0 ? 10 : 0,
            color:
              job.state === "succeeded"
                ? "#7bf2a8"
                : job.state === "partial"
                ? "#ffd08a"
                : "var(--color-red)",
          }}
        >
          {job.state === "succeeded" && `✓ Uploaded ${total} file${total !== 1 ? "s" : ""}`}
          {job.state === "partial" &&
            `⚠ Uploaded ${succeededCount} of ${total} — ${failedFiles.length} failed`}
          {job.state === "failed" && `✕ Upload failed — 0 of ${total} uploaded`}
        </div>
      )}

      {isTerminal && failedFiles.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          {failedFiles.map((f) => (
            <div
              key={`${f.source_id}:${f.index}`}
              style={{
                fontSize: 12,
                color: "var(--color-muted)",
                background: "#1c1608",
                border: "1px solid #3a2c10",
                borderRadius: 8,
                padding: "6px 10px",
              }}
            >
              <b style={{ color: "var(--color-text)" }}>{f.filename}</b>
              {f.error ? ` — ${f.error}` : ""}
            </div>
          ))}
        </div>
      )}

      {isTerminal && failedFiles.length > 0 && (
        <button
          onClick={handleRetry}
          disabled={retrying}
          style={{
            fontSize: 12.5,
            fontWeight: 700,
            color: "#fff",
            background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
            border: "none",
            padding: "8px 14px",
            borderRadius: 9,
            cursor: retrying ? "not-allowed" : "pointer",
            opacity: retrying ? 0.7 : 1,
          }}
        >
          {retrying ? "Retrying…" : `↻ Retry failures (${failedFiles.length})`}
        </button>
      )}

      {retryError && (
        <div style={{ fontSize: 12, color: "var(--color-red)", marginTop: 8 }}>{retryError}</div>
      )}
    </div>
  );
}
