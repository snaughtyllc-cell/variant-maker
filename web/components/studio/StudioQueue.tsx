"use client";
import type { QueueSnapshot } from "@/lib/types";
import { queueHeadline, queueRowLabel, queueWaitCopy } from "@/lib/queue";

export function StudioQueueCard({
  queue,
  qualityMode,
  jobId,
}: {
  queue: QueueSnapshot;
  qualityMode: "fast" | "hq";
  jobId?: string | null;
}) {
  return (
    <div
      style={{
        margin: "0 0 14px",
        padding: "10px 12px",
        background: "var(--color-panel2)",
        border: "1px solid var(--color-line)",
        borderRadius: 10,
        fontSize: 12,
        lineHeight: 1.45,
        color: "var(--color-muted)",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: ".5px",
          textTransform: "uppercase",
          color: "var(--color-muted2)",
          marginBottom: 6,
        }}
      >
        {queueHeadline(queue)}
      </div>
      {queue.jobs.length > 0 && (
        <ul style={{ margin: "0 0 8px", padding: "0 0 0 0", listStyle: "none" }}>
          {queue.jobs.map((job) => {
            const mine = job.job_id === jobId;
            return (
              <li
                key={job.job_id}
                style={{
                  margin: "0 0 4px",
                  color: mine ? "var(--color-text)" : "var(--color-muted)",
                  fontWeight: mine ? 650 : 500,
                }}
              >
                {queueRowLabel(job)}
                {mine ? " · you" : ""}
              </li>
            );
          })}
        </ul>
      )}
      <p style={{ margin: 0 }}>{queueWaitCopy(queue, qualityMode, jobId)}</p>
    </div>
  );
}
