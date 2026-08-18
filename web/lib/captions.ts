/** Caption bank helpers. Repurpose.io uses the Drive filename (minus .mp4) as the post. */

export function splitCaptionBank(raw: string): string[] {
  return (raw ?? "")
    .split(/^\s*---\s*$/m)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function captionFilenamePreview(text: string, fallback = "v01.mp4"): string {
  const stem = (text ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\n/g, " ")
    .replace(/[/\\\u0000-\u001f]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[ .]+|[ .]+$/g, "")
    .replace(/\.mp4$/i, "")
    .replace(/[ .]+$/g, "")
    .slice(0, 240)
    .replace(/[ .]+$/g, "");
  return stem ? `${stem}.mp4` : fallback;
}
