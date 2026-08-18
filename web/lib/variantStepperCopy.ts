/** Studio variant-count defaults and Fast-path helper copy. */

export const DEFAULT_PER_VIDEO = 10;
/** Stepper ceiling — usual Fast pack is ~20; leave room to tap up. */
export const MAX_PER_VIDEO = 40;

export function variantStepperHint(qualityMode: "fast" | "hq"): string | null {
  if (qualityMode !== "fast") return null;
  return "Usual pack is ~20 — tap + to go up.";
}
