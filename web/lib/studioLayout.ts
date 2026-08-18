export function studioShellClass(hasJob: boolean): string {
  return hasJob ? "studio-shell studio-shell--live" : "studio-shell";
}

export function studioProgressIdleClass(hasJob: boolean): string {
  return hasJob ? "studio-progress" : "studio-progress studio-progress--idle";
}
