import { isFileReady } from "./gallery";

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

export function shareVideosLabel(canShare: boolean): string {
  return canShare ? "Share videos" : "Save videos";
}

export function zipSecondaryCopy(): string {
  return "Desktop ZIP of the pack. On a phone, Save or Share videos instead — that skips the Files-app unzip.";
}

export function phoneShareHintCopy(): string {
  return "Saves or shares the mp4s so you can post without unzipping in Files.";
}

export function shareEmptyCopy(): string {
  return "Those videos never copied back from the GPU. Wait a moment and try again, or Regenerate.";
}
