/** Desktop live/progress rail — mock width, not the leftover column. */
export const STUDIO_LIVE_RAIL_PX = 400;

/** Phone live/progress strip. Tiles scroll inside; the rail does not grow. */
export const STUDIO_LIVE_PHONE_HEIGHT_PX = 240;

export function studioShellClass(_hasJob?: boolean): string {
  return "studio-shell";
}

export function studioProgressIdleClass(hasJob: boolean): string {
  return hasJob ? "studio-progress" : "studio-progress studio-progress--idle";
}
