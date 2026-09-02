import type { QueueItem, QueueSnapshot } from "./types";

/** iPhone uploads often land as stem_proxy.mp4 after normalize — show the clip name. */
export function displayClipName(filename: string): string {
  return filename.replace(/_proxy(?=\.[^.]+$)/, "");
}

export function jobsAhead(queue: QueueSnapshot, myJobId?: string | null): number {
  if (!myJobId) return queue.running;
  const mine = queue.jobs.find((j) => j.job_id === myJobId);
  if (!mine) return queue.running;
  return Math.max(0, mine.position - 1);
}

export function queueHeadline(queue: QueueSnapshot): string {
  if (queue.running === 0) return "Studio is free";
  if (queue.running === 1) return "1 pack generating";
  return `${queue.running} packs generating`;
}

export function queueOccupiesHq(job: {
  quality_mode?: string;
  prep_mode?: string;
  prep_status?: string | null;
}): boolean {
  if (job.quality_mode === "hq") return true;
  return job.prep_mode === "hq" && job.prep_status !== "done";
}

export function queueRowLabel(job: QueueItem): string {
  const names = job.filenames.map(displayClipName).join(", ") || "clip";
  const mode = queueOccupiesHq(job) ? "HQ" : "Fast";
  return `${job.position}. ${mode} · ${names} · ${job.delivered}/${job.requested}`;
}

export function queueStripLabel(queue: QueueSnapshot): string | null {
  if (queue.running === 0) return null;
  if (queue.running === 1 && queue.jobs[0]) {
    const j = queue.jobs[0];
    const mode = queueOccupiesHq(j) ? "HQ" : "Fast";
    return `1 gen · ${mode} ${j.delivered}/${j.requested}`;
  }
  return `${queue.running} generating`;
}

export function queueWaitCopy(
  queue: QueueSnapshot,
  qualityMode: "fast" | "hq",
  myJobId?: string | null,
): string {
  const mine = myJobId ? queue.jobs.find((j) => j.job_id === myJobId) : undefined;
  if (queue.running === 0) {
    return "Nobody else is generating. Fast packs from this shared URL run side by side and do not overwrite each other.";
  }
  const otherHq = queue.hq - (mine && queueOccupiesHq(mine) ? 1 : 0);
  if (qualityMode === "hq") {
    if (otherHq > 0) {
      const verb = otherHq === 1 ? "is" : "are";
      const behind = otherHq === 1 ? "it" : "them";
      return `${otherHq} HQ pack${otherHq === 1 ? "" : "s"} ${verb} on the GPU. Another HQ waits behind ${behind}. Fast still starts immediately.`;
    }
    return "HQ is on the one GPU. Fast packs from someone else still run at the same time.";
  }
  if (queue.hq > 0) {
    const n = queue.running;
    return `${n} pack${n === 1 ? "" : "s"} generating. Your Fast pack still starts now — it does not wait behind HQ.`;
  }
  const n = queue.running;
  return `${n} Fast pack${n === 1 ? "" : "s"} generating. Yours still starts now — Fast does not wait in a single line.`;
}
