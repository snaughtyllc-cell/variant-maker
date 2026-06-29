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
