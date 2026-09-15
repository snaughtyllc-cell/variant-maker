import { previewTime } from "./media";

const POSTER_MAX_EDGE = 360;
const posterCache = new Map<string, string>();
const posterInflight = new Map<string, Promise<string>>();
let captureChain: Promise<unknown> = Promise.resolve();

export function resetVideoPosterCache(): void {
  posterCache.clear();
  posterInflight.clear();
  captureChain = Promise.resolve();
}

export function filePosterKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

/** Large phone recordings need longer than 4s to decode a first frame. */
export function posterTimeoutMs(file: File): number {
  const mb = Math.max(0, file.size / (1024 * 1024));
  return Math.min(25_000, 8_000 + Math.ceil(mb) * 40);
}

/**
 * Decode one frame of a local File into a JPEG data URL.
 * Source cards and caption cards share one in-flight capture per file.
 */
export function captureVideoPoster(file: File, timeoutMs?: number): Promise<string> {
  const key = filePosterKey(file);
  const cached = posterCache.get(key);
  if (cached) return Promise.resolve(cached);
  const existing = posterInflight.get(key);
  if (existing) return existing;

  const wait = timeoutMs ?? posterTimeoutMs(file);
  const job = enqueue(() => captureVideoPosterOnce(file, wait))
    .then((dataUrl) => {
      posterCache.set(key, dataUrl);
      return dataUrl;
    })
    .finally(() => {
      posterInflight.delete(key);
    });
  posterInflight.set(key, job);
  return job;
}

function enqueue<T>(fn: () => Promise<T>): Promise<T> {
  const run = captureChain.then(fn, fn);
  captureChain = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

function captureVideoPosterOnce(file: File, timeoutMs: number): Promise<string> {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  video.setAttribute("playsinline", "");
  video.setAttribute("webkit-playsinline", "");
  video.setAttribute("aria-hidden", "true");
  video.tabIndex = -1;
  video.style.cssText =
    "position:fixed;left:-9999px;top:0;width:2px;height:2px;opacity:0;pointer-events:none";

  return new Promise<string>((resolve, reject) => {
    let settled = false;
    let seeking = false;

    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeAttribute("src");
      video.load();
      video.remove();
      URL.revokeObjectURL(url);
    };

    const fail = (reason: string) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new Error(reason));
    };

    const snap = () => {
      if (settled) return;
      const w = video.videoWidth;
      const h = video.videoHeight;
      if (!w || !h) return;
      const scale = Math.min(1, POSTER_MAX_EDGE / Math.max(w, h));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(w * scale));
      canvas.height = Math.max(1, Math.round(h * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        fail("no-canvas");
        return;
      }
      try {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const poster = canvas.toDataURL("image/jpeg", 0.72);
        if (!poster || poster === "data:,") {
          fail("empty-poster");
          return;
        }
        settled = true;
        cleanup();
        resolve(poster);
      } catch {
        fail("draw");
      }
    };

    const seekToPreview = () => {
      if (settled || seeking) return;
      seeking = true;
      const t = Math.min(previewTime(video.duration), 0.08);
      video.addEventListener("seeked", snap, { once: true });
      const rvfc = (
        video as HTMLVideoElement & {
          requestVideoFrameCallback?: (cb: () => void) => void;
        }
      ).requestVideoFrameCallback;
      if (typeof rvfc === "function") {
        rvfc.call(video, snap);
      }
      try {
        if (Math.abs(video.currentTime - t) < 0.02) {
          video.currentTime = t === 0 ? 0.01 : 0;
        }
        video.currentTime = t;
      } catch {
        snap();
      }
    };

    const timer = window.setTimeout(() => fail("timeout"), timeoutMs);
    video.addEventListener("error", () => fail("load"), { once: true });
    video.addEventListener("loadedmetadata", seekToPreview, { once: true });
    video.addEventListener("loadeddata", seekToPreview, { once: true });

    document.body.appendChild(video);
    video.src = url;
    video.load();
  });
}
