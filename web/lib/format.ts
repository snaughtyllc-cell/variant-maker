import { DiagnosticsItem, VMAF_FLOOR } from "./types";

export function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}
export function vmafPass(v: number): boolean { return v >= VMAF_FLOOR; }

/** Path-B cheap readout: same SSIM-bits scale as uniqueness (similarity = 1 − uniqueness). */
export function similarityFromUniqueness(uniqueness: number): number {
  return 1 - uniqueness;
}

export function pct01(v: number): number {
  return Math.round(Math.min(1, Math.max(0, v)) * 100);
}

export function diagnosticsReason(d: DiagnosticsItem): { title: string; metric: string; corrupt: boolean } {
  if (d.status === "corrupt" || d.quality.spatial_ok === false) {
    const sv = d.quality.spatial_vmaf ?? 0;
    return {
      title: "Neural upscale tore the frame (spatial-corruption guard)",
      metric: `Spatial VMAF ${sv.toFixed(1)} < corruption floor · rejected before delivery`,
      corrupt: true,
    };
  }
  return {
    title: "Quality stayed under the floor after 3 re-rolls",
    metric: `VMAF ${d.quality.vmaf.toFixed(1)} < floor ${VMAF_FLOOR} · histogram ${d.quality.histogram_ok ? "OK" : "fail"}`,
    corrupt: false,
  };
}
