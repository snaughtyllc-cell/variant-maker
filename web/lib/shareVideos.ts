import { isFileReady } from "./gallery";
import type { SourceOut } from "./types";

export type ShareNavigatorLike = {
  canShare?: (data?: { files?: File[] }) => boolean;
  share?: (data: { files?: File[]; title?: string; text?: string }) => Promise<void>;
};

export type ShareFn = (data: { files: File[]; title?: string }) => Promise<void>;

export type ShareVideoResult = "shared" | "aborted" | "unsupported";

export type ShareableVariant = {
  filename: string;
  file_url?: string;
  file_ready?: boolean;
  status?: string;
};

export type SaveOrShareResult = ShareVideoResult | "downloaded";

function isAbortError(err: unknown): boolean {
  return typeof err === "object" && err !== null && "name" in err && (err as { name: string }).name === "AbortError";
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

export async function shareVideoFiles(
  files: File[],
  shareFn?: ShareFn,
): Promise<ShareVideoResult> {
  if (!shareFn || files.length === 0) return "unsupported";
  try {
    await shareFn({ files });
    return "shared";
  } catch (err) {
    if (isAbortError(err)) return "aborted";
    return "unsupported";
  }
}

export async function shareVideoFilesSequentially(
  files: File[],
  shareFn?: ShareFn,
): Promise<ShareVideoResult> {
  if (!shareFn || files.length === 0) return "unsupported";
  let shared = 0;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    try {
      await shareFn({ files: [file], title: file.name });
      shared += 1;
    } catch (err) {
      if (isAbortError(err)) return shared > 0 ? "shared" : "aborted";
      if (shared === 0) return "unsupported";
      const rest = files.slice(i);
      const leftover = await shareVideoFiles(rest, shareFn);
      if (leftover === "shared" || leftover === "aborted") return "shared";
      return "unsupported";
    }
  }
  return "shared";
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
    const res = await fetchFn(variant.file_url);
    if (!res.ok) continue;
    const buf = await res.arrayBuffer();
    const type = (res.headers.get("content-type") || "video/mp4").split(";")[0] || "video/mp4";
    files.push(new File([buf], variant.filename, { type }));
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

export async function saveOrShareVideoFiles(
  files: File[],
  options?: {
    share?: ShareNavigatorLike | null;
    download?: (files: File[]) => void;
  },
): Promise<SaveOrShareResult> {
  if (files.length === 0) return "unsupported";
  const shareNav = options?.share;
  const shareFn =
    shareNav && typeof shareNav.share === "function" ? shareNav.share.bind(shareNav) : undefined;
  const probe = files.slice(0, 1);
  if (shareFn && canShareVideoFiles(shareNav, probe)) {
    const result = await shareVideoFilesSequentially(files, shareFn);
    if (result === "shared" || result === "aborted") return result;
  }
  (options?.download ?? downloadVideoFiles)(files);
  return "downloaded";
}

export function shareVideosLabel(canShare: boolean): string {
  return canShare ? "Save to Photos" : "Save to phone";
}

export function shareVideosBusyLabel(): string {
  return "Saving…";
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
  return "Opens the share sheet. Tap Save Video to put the clip in Photos — not Files.";
}

export function shareEmptyCopy(): string {
  return "Those videos never copied back from the GPU. Wait a moment and try again, or Regenerate.";
}

export function saveNoneSelectedCopy(): string {
  return "Select clips first";
}
