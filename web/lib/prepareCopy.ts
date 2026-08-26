export const PREPARING_JOB_ID = "preparing";

export function isPreparingJob(jobId: string | null | undefined): boolean {
  return jobId === PREPARING_JOB_ID;
}

export function preparingHeadline(): string {
  return "Preparing generation";
}

export function preparingSubcopy(): string {
  return "Request received. The processing environment can take 20–30 seconds to start — tiles update as soon as encoding begins.";
}

export function preparingSlotLabel(): string {
  return "starting";
}

export function captionToggleLabel(): string {
  return "Write captions for these copies";
}

export function captionToggleHint(): string {
  return "AI writes a post caption per variant. Preview them in Gallery under each clip.";
}

export function captionPreviewLabel(): string {
  return "Caption";
}

export function captionEmptyCopy(): string {
  return "No caption on this copy yet.";
}

export function uniquenessCustomerLabel(): string {
  return "Originality";
}

export function captionSnippet(text: string | null | undefined, max = 80): string {
  const one = (text || "").replace(/\s+/g, " ").trim();
  if (!one) return "";
  if (one.length <= max) return one;
  return `${one.slice(0, Math.max(1, max - 1)).trimEnd()}…`;
}
