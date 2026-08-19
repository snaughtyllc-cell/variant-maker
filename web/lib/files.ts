export const MAX_UPLOAD_BYTES = 512 * 1024 * 1024; // 512 MB — iPhone 4K HEVC shorts

export function accepts(file: File): boolean {
  if (file.type.startsWith("video/")) return true;
  return /\.(mp4|mov|m4v|webm)$/i.test(file.name);
}

export function tooLargeMessage(file: File): string | null {
  if (file.size <= MAX_UPLOAD_BYTES) return null;
  const mb = (file.size / (1024 * 1024)).toFixed(0);
  return (
    `${file.name} is ${mb} MB — over the 512 MB drop limit. ` +
    "Trim the clip or export 1080p H.264, then drop that file. " +
    "4K under 512 MB is fine; we shrink it after upload."
  );
}

export function totalVariants(fileCount: number, perVideo: number): number {
  return fileCount * perVideo;
}

export function readDurations(files: File[]): Promise<number[]> {
  return Promise.all(
    files.map(
      (f) =>
        new Promise<number>((resolve) => {
          const v = document.createElement("video");
          v.preload = "metadata";
          v.onloadedmetadata = () => {
            URL.revokeObjectURL(v.src);
            resolve(v.duration || 0);
          };
          v.onerror = () => resolve(0);
          v.src = URL.createObjectURL(f);
        })
    )
  );
}
