/**
 * Operator How-to copy: case scenarios and posting hygiene, not a Generate
 * walkthrough. Never fingerprint internals (SHA / AAC / SEI / encode tags).
 * Tests scan this module.
 */

export type HowToSection = {
  id: string;
  title: string;
  paragraphs: string[];
  bullets?: string[];
};

export const HOW_TO_TITLE = "How to";
export const HOW_TO_EYEBROW = "Best practices";
export const HOW_TO_LEAD =
  "How to run packs well — Studio to Gallery, Workflows, posting, and the schedulers you already use. Not a click-by-click of Generate.";

export const HOW_TO_SECTIONS: HowToSection[] = [
  {
    id: "studio",
    title: "Studio → Gallery",
    paragraphs: [
      "Start from the original master. Drop it on Studio or pick it from Drive. Generate a Fast pack, then open Gallery and check the look before anything goes out.",
      "Do not run a finished copy through Studio as a new source. That stacks encodes and the look gets worse.",
    ],
  },
  {
    id: "workflows",
    title: "Workflows",
    paragraphs: [
      "Drive in, Drive out. Save two folders: an inbox for raw clips and a different output folder for finished packs. Share the studio Drive email as Editor so the machine can actually open them.",
      "A workflow watches the inbox, makes the pack, and drops copies into output — one subfolder per source, not one giant pile.",
    ],
  },
  {
    id: "posting",
    title: "Posting",
    paragraphs: [
      "If you post the same pack across multiple accounts, do not drop every copy on every account at the same time. Stagger. Flags, integrity issues, and bans stack when a whole set lands at once.",
      "Trial Reels: skip sexual clips. If one of those gets flagged, a lot of them get flagged — then you have a pile of sexual flags on the account. The usual miss with copies is not the file itself getting the account banned. It is using the wrong kind of content, then posting that same content over and over so flags pile up.",
    ],
  },
  {
    id: "automation",
    title: "Automation",
    paragraphs: [
      "You do not have to post by hand. Point the export Drive folder at Repurpose.io or Buffer and let that tool schedule.",
      "Repurpose reads the Drive filename as the caption — set captions in Drive before the handoff. We do not run those seats; we hand off the folder.",
    ],
  },
];

export const HOW_TO_JUMP_LINKS = [
  { href: "/", label: "Studio" },
  { href: "/gallery", label: "Gallery" },
  { href: "/workflows", label: "Workflows" },
  { href: "/settings/drive", label: "Drive" },
] as const;

/** Patterns that must never appear in How-to (clone bait / internals). */
export const HOW_TO_FORBIDDEN: readonly RegExp[] = [
  /\bSHA-?256\b/i,
  /\bSHA\b/,
  /\bAAC\b/,
  /\bSEI\b/,
  /\bSSIM\b/i,
  /\bVMAF\b/i,
  /\bMAE\b/,
  /fingerprint/i,
  /\bx264\b/i,
  /\blibx264\b/i,
  /\bgate\s*24\b/i,
  /\b24\s*bits\b/i,
  /38%/,
  /\bdetector\b/i,
  /nal_hrd/i,
  /info=0/i,
];

export function howToPlainText(): string {
  const parts = [HOW_TO_TITLE, HOW_TO_EYEBROW, HOW_TO_LEAD];
  for (const section of HOW_TO_SECTIONS) {
    parts.push(section.title, ...section.paragraphs, ...(section.bullets ?? []));
  }
  parts.push(...HOW_TO_JUMP_LINKS.map((link) => link.label));
  return parts.join("\n");
}
