export const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024; // 1 GB — iPhone 4K HEVC from Camera Roll

export function accepts(file: File): boolean {
  if (file.type.startsWith("video/")) return true;
  return /\.(mp4|mov|m4v|webm)$/i.test(file.name);
}

export function tooLargeMessage(file: File): string | null {
  if (file.size <= MAX_UPLOAD_BYTES) return null;
  const mb = (file.size / (1024 * 1024)).toFixed(0);
  return (
    `${file.name} is ${mb} MB — over the 1 GB iPhone drop limit. ` +
    "Trim it in Photos, then pick it from Camera Roll again."
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
