/** Caption bank helpers. Repurpose.io uses the Drive filename (minus .mp4) as the post. */

const DASH_LINE = /^\s*---\s*$/m;
const LEADING_BULLET = /^(?:\d+[.)]\s+|[-*]\s+)/;

export function splitCaptionBank(raw: string): string[] {
  let text = (raw ?? "").trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```[^\n]*\n/, "").replace(/\n```\s*$/, "");
  }
  const parts = DASH_LINE.test(text)
    ? text.split(DASH_LINE)
    : text.split(/\n\s*\n/);
  return parts
    .map((part) => part.trim().replace(LEADING_BULLET, "").trim())
    .filter(Boolean);
}

export function captionBankChatPrompt(opts?: { count?: number; topic?: string }): string {
  const rawCount = opts?.count ?? 20;
  const count = Math.min(100, Math.max(1, Math.floor(Number(rawCount) || 20)));
  const topic = (opts?.topic ?? "").trim() || "short UGC / POV Reels (dating, thirst, lifestyle)";
  return [
    "Write Instagram Reels / TikTok captions for short UGC clips.",
    "",
    `Topic: ${topic}`,
    `Write ${count} captions.`,
    "",
    "Output ONLY the captions. No intro, no outro, no quotes, do not number them.",
    "Separate every caption with a line that is exactly:",
    "---",
    "",
    "Each caption:",
    "- 1–2 short hook lines (POV: is fine; keep the colon)",
    "- Then 3–8 hashtags on the last lines",
    "- No / or \\ characters (they break Google Drive filenames)",
    "- No markdown fences",
    "",
    "Save the reply as a .txt if you can. I will import it into a caption bank.",
  ].join("\n");
}

export const CAPTION_PACK_SIZE = 20;

export function captionFolderCountLabel(count: number, remaining: number): string {
  if (count <= 0) return "0 left";
  return `${remaining} left · ${count} total`;
}

export const CUSTOM_CAPTION_SOURCE = "";

export function isCustomCaptionSource(bankId: string | null | undefined): boolean {
  return !bankId;
}

export function captionCustomSourceLabel(): string {
  return "Custom — write the filename";
}

export function captionFolderSelectLabel(
  name: string,
  count: number,
  remaining: number,
): string {
  if (count <= 0) return `${name} — 0 left`;
  return `${name} — ${remaining} left`;
}

export function captionFolderLowCopy(
  count: number,
  remaining: number,
  pack = CAPTION_PACK_SIZE,
): string | null {
  if (count <= 0) return "Empty — add captions or exports keep v01.mp4 names.";
  if (remaining < pack) {
    return `Low — ${remaining} left before this folder repeats. A ${pack}-pack will reuse lines.`;
  }
  return null;
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
