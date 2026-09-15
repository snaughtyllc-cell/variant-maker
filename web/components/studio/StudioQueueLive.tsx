"use client";
import { useState } from "react";
import { cancelJob } from "@/lib/api";
import { useQueue } from "@/lib/useQueue";
import { StudioQueueCard } from "./StudioQueue";

export function StudioQueue({
  qualityMode,
  jobId,
}: {
  qualityMode: "fast" | "hq";
  jobId?: string | null;
}) {
  const { data, mutate } = useQueue();
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  async function handleCancel(id: string) {
    if (cancellingId) return;
    setCancellingId(id);
    try {
      await cancelJob(id);
      await mutate();
    } catch {
      // Poll will drop the row once the job closes.
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <StudioQueueCard
      queue={data}
      qualityMode={qualityMode}
      jobId={jobId}
      onCancel={handleCancel}
      cancellingId={cancellingId}
    />
  );
}
