/** Operator-facing week readout. Packs stay attributed to the signed-in email. */

export type UsageTone = "included" | "usage";

export type SidebarUsage = { pct: number; label: string; tone: UsageTone };

export function sidebarUsage(
  usage:
    | {
        uncapped?: boolean;
        tone?: UsageTone | string | null;
        remaining_pct?: number | null;
        meter_line?: string | null;
        label?: string | null;
      }
    | null
    | undefined,
): SidebarUsage | null {
  if (!usage || usage.uncapped) return null;
  const tone: UsageTone = usage.tone === "usage" ? "usage" : "included";
  const label = (usage.meter_line || usage.label || "").trim();
  if (!label && usage.remaining_pct == null) return null;
  const pct = Math.max(0, Math.min(100, Math.round(usage.remaining_pct ?? (tone === "usage" ? 0 : 100))));
  return { pct, label: label || (tone === "usage" ? "Usage" : "0h left"), tone };
}

export function memberWeekCopy(member: {
  week_fast?: number;
  week_hq?: number;
  week_packs?: number;
}): string {
  const fast = member.week_fast ?? 0;
  const hq = member.week_hq ?? 0;
  const packs = member.week_packs ?? 0;
  if (fast === 0 && hq === 0 && packs === 0) return "This week: no packs";
  const packLabel = packs === 1 ? "1 pack" : `${packs} packs`;
  return `This week: ${fast} Fast · ${hq} HQ · ${packLabel}`;
}
