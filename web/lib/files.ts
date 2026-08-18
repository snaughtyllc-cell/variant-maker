export const MAX_UPLOAD_BYTES = 120 * 1024 * 1024; // 120 MB

export function accepts(file: File): boolean {
  if (file.type.startsWith("video/")) return true;
  return /\.(mp4|mov|m4v|webm)$/i.test(file.name);
}

export function tooLargeMessage(file: File): string | null {
  if (file.size <= MAX_UPLOAD_BYTES) return null;
  const mb = (file.size / (1024 * 1024)).toFixed(0);
  return `${file.name} is ${mb} MB — too large. Export 1080p H.264 (typical 8–15s clips are well under 120 MB), then drop that file.`;
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
