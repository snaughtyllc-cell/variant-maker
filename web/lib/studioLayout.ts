/** Desktop live/progress rail — fixed column, slightly roomier than 400. */
export const STUDIO_LIVE_RAIL_PX = 460;

export function studioShellClass(_hasJob?: boolean): string {
  return "studio-shell";
}

export function studioProgressIdleClass(hasJob: boolean): string {
  return hasJob ? "studio-progress" : "studio-progress studio-progress--idle";
}
