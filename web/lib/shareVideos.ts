import { isFileReady } from "./gallery";
import type { SourceOut } from "./types";

export type ShareNavigatorLike = {
  canShare?: (data?: { files?: File[] }) => boolean;
  share?: (data: { files?: File[]; title?: string; text?: string }) => Promise<void>;
};

export type ShareFn = (data: { files: File[] }) => Promise<void>;

export type ShareVideoResult = "shared" | "aborted" | "unsupported";

export type ShareableVariant = {
  filename: string;
  file_url?: string;
  file_ready?: boolean;
  status?: string;
};

export type SaveOrShareResult = ShareVideoResult | "downloaded" | "needs_gesture";

export type SaveOrShareOutcome = {
  result: SaveOrShareResult;
  remaining: File[];
  reason?: "retry";
};

export type VariantFileRef = { file_url: string; filename: string };

function isAbortError(err: unknown): boolean {
  return typeof err === "object" && err !== null && "name" in err && (err as { name: string }).name === "AbortError";
}

export function isAppleMobile(ua = "", maxTouchPoints = 0): boolean {
  if (/iPhone|iPad|iPod/.test(ua)) return true;
  return /Macintosh/.test(ua) && maxTouchPoints > 1;
}

export function hasShareMethod(share?: ShareNavigatorLike | null): boolean {
  return Boolean(share && typeof share.share === "function");
}

export function shouldOfferPhotosSave(
  share?: ShareNavigatorLike | null,
  ua = "",
  maxTouchPoints = 0,
): boolean {
  return hasShareMethod(share) || canShareVideoFiles(share) || isAppleMobile(ua, maxTouchPoints);
}

export function canShareVideoFiles(
  share?: ShareNavigatorLike | null,
  files?: File[],
): boolean {
  if (!share || typeof share.canShare !== "function") return false;
  if (typeof File === "undefined") return false;
  try {
    const probe =
      files && files.length > 0
        ? files
        : [new File(["x"], "probe.mp4", { type: "video/mp4" })];
    return share.canShare({ files: probe }) === true;
  } catch {
    return false;
  }
}

export function cloneShareFiles(files: File[]): File[] {
  return files.map((file) => {
    const name = file.name.toLowerCase().endsWith(".mp4") ? file.name : `${file.name}.mp4`;
    return new File([file], name, { type: "video/mp4", lastModified: Date.now() });
  });
}

export async function shareVideoFiles(
  files: File[],
  shareFn?: ShareFn,
): Promise<ShareVideoResult> {
  if (!shareFn || files.length === 0) return "unsupported";
  try {
    // Files only — title/text/url on iOS often routes the sheet to Files or Drive.
    await shareFn({ files: cloneShareFiles(files) });
    return "shared";
  } catch (err) {
    if (isAbortError(err)) return "aborted";
    return "unsupported";
  }
}

export function isShareableVideo<T extends ShareableVariant>(
  variant: T,
): variant is T & { file_url: string } {
  if (!isFileReady(variant)) return false;
  if (variant.status != null && variant.status !== "ok") return false;
  return Boolean(variant.file_url);
}

export function readyShareableVariants<T extends ShareableVariant>(
  variants: T[],
): Array<T & { file_url: string }> {
  return variants.filter(isShareableVideo);
}

export function selectedShareableVariants(
  sources: SourceOut[],
  selected: Set<string>,
): Array<{ file_url: string; filename: string }> {
  const out: Array<{ file_url: string; filename: string }> = [];
  for (const source of sources) {
    for (const variant of source.variants) {
      if (!selected.has(`${source.source_id}:${variant.index}`)) continue;
      if (!isShareableVideo(variant)) continue;
      out.push({ file_url: variant.file_url, filename: variant.filename });
    }
  }
  return out;
}

export async function fetchVariantFiles(
  variants: { file_url: string; filename: string }[],
  fetchFn: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<File[]> {
  const files: File[] = [];
  for (const variant of variants) {
    try {
      const res = await fetchFn(variant.file_url);
      if (!res || !res.ok) continue;
      const buf = await res.arrayBuffer();
      const name = variant.filename.toLowerCase().endsWith(".mp4")
        ? variant.filename
        : `${variant.filename}.mp4`;
      files.push(new File([buf], name, { type: "video/mp4" }));
    } catch {
      continue;
    }
  }
  return files;
}

export function downloadVideoFiles(
  files: File[],
  click?: (anchor: HTMLAnchorElement) => void,
): void {
  const trigger = click ?? ((a) => a.click());
  for (const file of files) {
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    a.rel = "noopener";
    document.body.appendChild(a);
    trigger(a);
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
}

export function peekCachedFiles(
  cache: Map<string, File>,
  variants: VariantFileRef[],
): File[] {
  const files: File[] = [];
  for (const variant of variants) {
    const hit = cache.get(variant.file_url);
    if (!hit) return [];
    files.push(hit);
  }
  return files;
}

export function cacheHasAll(cache: Map<string, File>, variants: VariantFileRef[]): boolean {
  return variants.length > 0 && variants.every((variant) => cache.has(variant.file_url));
}

export async function fillFileCache(
  cache: Map<string, File>,
  variants: VariantFileRef[],
  fetchFn: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<File[]> {
  const missing = variants.filter((variant) => !cache.has(variant.file_url));
  if (missing.length > 0) {
    const fetched = await fetchVariantFiles(missing, fetchFn);
    const byName = new Map(fetched.map((file) => [file.name, file]));
    for (const variant of missing) {
      const want = variant.filename.toLowerCase().endsWith(".mp4")
        ? variant.filename
        : `${variant.filename}.mp4`;
      const file = byName.get(want) ?? byName.get(variant.filename);
      if (file) cache.set(variant.file_url, file);
    }
  }
  return variants.map((variant) => cache.get(variant.file_url)).filter((file): file is File => Boolean(file));
}

export function filesReadyNow(
  cache: Map<string, File>,
  variants: VariantFileRef[],
  pending?: File[] | null,
): File[] | null {
  if (pending && pending.length > 0) return pending;
  if (cacheHasAll(cache, variants)) return peekCachedFiles(cache, variants);
  return null;
}

export async function saveOrShareVideoFiles(
  files: File[],
  options?: {
    share?: ShareNavigatorLike | null;
    download?: (files: File[]) => void;
    userAgent?: string;
    maxTouchPoints?: number;
  },
): Promise<SaveOrShareOutcome> {
  if (files.length === 0) return { result: "unsupported", remaining: [] };
  const ua =
    options?.userAgent ??
    (typeof navigator === "undefined" ? "" : navigator.userAgent);
  const touch =
    options?.maxTouchPoints ??
    (typeof navigator === "undefined" ? 0 : navigator.maxTouchPoints);
  const apple = isAppleMobile(ua, touch);
  const shareNav = options?.share;
  const shareFn =
    shareNav && typeof shareNav.share === "function" ? shareNav.share.bind(shareNav) : undefined;
  if (shareFn) {
    const result = await shareVideoFiles(files, shareFn);
    if (result === "shared" || result === "aborted") {
      return { result, remaining: [] };
    }
    // Gesture dropped or WebKit spent the last share. Keep the mp4s for a
    // fresh tap — never <a download> on iPhone (that is Files).
    if (apple) return { result: "needs_gesture", remaining: files, reason: "retry" };
    (options?.download ?? downloadVideoFiles)(files);
    return { result: "downloaded", remaining: [] };
  }
  if (apple) return { result: "needs_gesture", remaining: files, reason: "retry" };
  (options?.download ?? downloadVideoFiles)(files);
  return { result: "downloaded", remaining: [] };
}

export function shareVideosLabel(offerPhotos: boolean): string {
  return offerPhotos ? "Save to Photos" : "Save to phone";
}

export function shareVideosBusyLabel(): string {
  return "Saving…";
}

export function preparingClipsCopy(): string {
  return "Preparing clips…";
}

export function zipVisibleOnDevice(
  matchMedia?: ((query: string) => { matches: boolean }) | null,
): boolean {
  return matchMedia?.("(pointer: coarse)")?.matches !== true;
}

export function zipSecondaryCopy(): string {
  return "Desktop ZIP of the pack. On a phone ZIP lands in Files — use Save to Photos instead.";
}

export function phoneShareHintCopy(): string {
  return "Select the clips, tap Save to Photos, then tap Save Videos on the share sheet. Skip Files and Drive.";
}

export function shareEmptyCopy(): string {
  return "Those videos never copied back from the GPU. Wait a moment and try again, or Regenerate.";
}

export function saveNoneSelectedCopy(): string {
  return "Select clips first";
}

export function shareRetryCopy(): string {
  return "Clips are ready. Tap Save to Photos again to open the share sheet — skip the Safari download.";
}

export function shareLoadingCopy(): string {
  return "Preparing clips… tap Save to Photos when this note is gone.";
}

export function shareOutcomeMessage(outcome: SaveOrShareOutcome): string | null {
  if (outcome.result !== "needs_gesture") return null;
  return shareRetryCopy();
}
