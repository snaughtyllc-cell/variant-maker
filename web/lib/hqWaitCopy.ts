/** Studio copy while HQ (Phase 8) sits on v01 with no thumb. */

export type QualityMode = "fast" | "hq";

export const HQ_RENDERING_HINT =
  "HQ upscales every frame — the first variant often takes several minutes with no thumb. That is not a hang.";

export function inFlightRenderingLabel(
  index: number,
  qualityMode: QualityMode = "fast",
): string {
  const idx = String(index).padStart(2, "0");
  if (qualityMode === "hq") {
    return `● v${idx} HQ upscaling…`;
  }
  return `● v${idx} rendering…`;
}

export function liveRunSubcopy(qualityMode: QualityMode = "fast"): string {
  if (qualityMode === "hq") {
    return `${HQ_RENDERING_HINT} Gallery stays empty until a variant finishes.`;
  }
  return "Live status updates every second. Stay here until tiles appear; Gallery stays empty until a variant finishes.";
}
