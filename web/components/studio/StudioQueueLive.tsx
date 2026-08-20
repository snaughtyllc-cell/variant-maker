"use client";
import { useQueue } from "@/lib/useQueue";
import { StudioQueueCard } from "./StudioQueue";

export function StudioQueue({
  qualityMode,
  jobId,
}: {
  qualityMode: "fast" | "hq";
  jobId?: string | null;
}) {
  const { data } = useQueue();
  return <StudioQueueCard queue={data} qualityMode={qualityMode} jobId={jobId} />;
}
