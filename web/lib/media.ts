/**
 * clipInset — returns a CSS clip-path inset string that reveals `pct`% of
 * the element from the left.  Used by CompareSlider's before-video layer.
 *
 * clipInset(54) → "inset(0 46% 0 0)"
 */
export function clipInset(pct: number): string {
  return `inset(0 ${100 - pct}% 0 0)`;
}

/**
 * clampTime — clamp a time value to [0, duration].
 * Returns 0 when duration is falsy or ≤ 0 (protects against un-loaded video).
 */
export function clampTime(t: number, duration: number): number {
  if (!duration || duration < 0) return 0;
  return Math.min(Math.max(t, 0), duration);
}

/** iOS Safari often shows a black <video> until a non-zero timestamp is decoded. */
export const PREVIEW_SECONDS = 0.15;

/**
 * Media-fragment URL so Safari can paint a first frame without hover-to-play.
 * Leaves an existing `#…` hash alone (caller already chose the fragment).
 */
export function videoFrameSrc(src: string, seconds: number = PREVIEW_SECONDS): string {
  const s = (src ?? "").trim();
  if (!s || s.includes("#")) return s;
  return `${s}#t=${seconds}`;
}

/** Timestamp to seek to so a poster frame exists. Tiny clips stay inside duration. */
export function previewTime(duration: number, fallback: number = PREVIEW_SECONDS): number {
  if (!Number.isFinite(duration) || duration <= 0) return fallback;
  return Math.min(fallback, duration * 0.25);
}

/** Decode one frame onto the element. Safe to call from loadedmetadata / loadeddata. */
export function paintVideoFrame(video: HTMLVideoElement | null): void {
  if (!video) return;
  video.setAttribute("playsinline", "");
  video.setAttribute("webkit-playsinline", "");
  const t = previewTime(video.duration);
  if (video.currentTime < 0.05) {
    try {
      video.currentTime = t;
    } catch {
      /* iOS may reject seek until more data arrives */
    }
  }
  const play = video.play();
  if (play && typeof play.then === "function") {
    play
      .then(() => {
        video.pause();
        const v = video as HTMLVideoElement & {
          webkitDisplayingFullscreen?: boolean;
          webkitExitFullscreen?: () => void;
        };
        if (v.webkitDisplayingFullscreen) v.webkitExitFullscreen?.();
      })
      .catch(() => {/* autoplay blocked */});
  }
}
