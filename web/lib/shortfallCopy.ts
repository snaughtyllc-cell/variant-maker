import { SourceOut } from "./types";

/** Gallery shortfall banner copy. Never send operators to Diagnostics. */
export function shortfallCopy(source: SourceOut): string | null {
  if (source.shortfall <= 0) return null;
  const n = source.shortfall;
  const plural = n === 1 ? "" : "s";
  if (source.job_state === "running" || source.in_flight) {
    return `Still rendering — ${source.delivered}/${source.requested} delivered so far.`;
  }
  if ((source.failed ?? 0) > 0) {
    return (
      `${n} variant${plural} fell short after auto-retry — quality/VMAF (best_effort), ` +
      `not the uniqueness %. Regenerate this pack to fill the gap.`
    );
  }
  return `${n} variant${plural} missing / not delivered — Regenerate to fill the gap.`;
}
