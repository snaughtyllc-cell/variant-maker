import { MAX_PER_VIDEO } from "./variantStepperCopy";
import type { AuthMe } from "./types";

/** null = unlimited (admins, auth off, or empty cap). */
export function copiesPerSourceMax(me: AuthMe | undefined): number {
  if (!me || me.auth_required === false || me.is_admin) return MAX_PER_VIDEO;
  const cap = me.variants_per_source_limit;
  if (typeof cap === "number" && cap > 0) return Math.min(MAX_PER_VIDEO, cap);
  return MAX_PER_VIDEO;
}

/** null = unlimited. Else remaining source clips in the trial cap. */
export function sourcesRemaining(me: AuthMe | undefined): number | null {
  if (!me || me.auth_required === false || me.is_admin) return null;
  if (me.source_limit == null) return null;
  return Math.max(0, me.source_limit - (me.sources_used ?? 0));
}

export function usagePair(sources: number | undefined, copies: number | undefined): string {
  const s = sources ?? 0;
  const c = copies ?? 0;
  if (s === 0 && c === 0) return "—";
  return `${s} src · ${c}`;
}

/** Short tester-facing line when Admin has set a trial cap. */
export function trialCapHint(me: AuthMe | undefined): string | null {
  if (!me || me.auth_required === false || me.is_admin) return null;
  const left = sourcesRemaining(me);
  const per = me.variants_per_source_limit;
  const bits: string[] = [];
  if (left !== null) {
    bits.push(
      left === 0
        ? "This studio has used its source cap."
        : `${left} source clip${left === 1 ? "" : "s"} left on this trial.`,
    );
  }
  if (typeof per === "number" && per > 0) {
    bits.push(`Max ${per} copies per clip.`);
  }
  return bits.length ? bits.join(" ") : null;
}
