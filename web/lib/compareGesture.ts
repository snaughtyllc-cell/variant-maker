export const COMPARE_TOUCH_THRESHOLD = 8;

export type CompareTouchIntent = "undecided" | "drag" | "scroll";

/**
 * Mouse/pen can slide the split immediately. Touch waits so a vertical
 * flick still scrolls the uniqueness sheet instead of stealing the gesture.
 */
export function startsCompareDragImmediately(pointerType: string): boolean {
  return pointerType !== "touch";
}

/** Classify a touch movement relative to where the finger went down. */
export function compareTouchIntent(
  dx: number,
  dy: number,
  threshold: number = COMPARE_TOUCH_THRESHOLD,
): CompareTouchIntent {
  if (Math.abs(dx) < threshold && Math.abs(dy) < threshold) return "undecided";
  if (Math.abs(dy) >= Math.abs(dx)) return "scroll";
  return "drag";
}

type CaptureEl = {
  hasPointerCapture?: (pointerId: number) => boolean;
  releasePointerCapture: (pointerId: number) => void;
};

/**
 * Always drop capture on pointerup/cancel. Leaving it held (common on iOS
 * when touch-action is pan-y) routes later taps to the slider, so Close /
 * prev / next in the sheet header stop working.
 */
export function releasePointerCaptureSafe(
  el: CaptureEl | null,
  pointerId: number,
): void {
  if (!el) return;
  try {
    if (typeof el.hasPointerCapture === "function" && !el.hasPointerCapture(pointerId)) {
      return;
    }
    el.releasePointerCapture(pointerId);
  } catch {
    /* already released, or the node never captured this pointer */
  }
}
