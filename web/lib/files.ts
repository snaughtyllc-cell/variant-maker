export function accepts(file: File): boolean {
  if (file.type.startsWith("video/")) return true;
  return /\.(mp4|mov|m4v|webm)$/i.test(file.name);
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
