/**
 * Operator How-to copy. Keep this page posting hygiene — never fingerprint
 * internals (SHA / AAC / SEI / encode tags). Tests scan this module.
 */

export type HowToSection = {
  id: string;
  title: string;
  paragraphs: string[];
  bullets?: string[];
};

export const HOW_TO_TITLE = "How to";
export const HOW_TO_EYEBROW = "Operator loop";
export const HOW_TO_LEAD =
  "One source clip in. Fast copies out. Check the look. Send to Drive. Post with space between copies. This page is how we run packs — not a promise about what Instagram will do.";

export const HOW_TO_SECTIONS: HowToSection[] = [
  {
    id: "source",
    title: "1. Start from the original",
    paragraphs: [
      "Use the master clip. Drop it on Studio or pick it from Drive.",
      "Do not run a finished copy through Studio as a new source. That stacks encodes and the look gets worse.",
      "Phone files are fine if they play. Convert only when it actually saves a huge upload wait.",
    ],
  },
  {
    id: "fast",
    title: "2. Make a Fast pack",
    paragraphs: [
      "On Studio, set how many copies and generate. Fast is the daily path.",
      "Reconstruct first (HQ) is optional and off by default. Turn it on when the source already looks soft — one GPU pass, then Fast. Not every pack, and not a 4K upscaler.",
    ],
  },
  {
    id: "look",
    title: "3. Check the look",
    paragraphs: [
      "Open Gallery. Compare stills to the source. If a copy looks washed, muddy, or unlike the clip, do not send it.",
      "Play the file when you are unsure. Stills are not the whole video.",
    ],
  },
  {
    id: "handoff",
    title: "4. Hand off",
    paragraphs: [
      "Send to Drive. Split a pack across folders if accounts need different files.",
      "Workflows can watch an inbox folder if you already drop sources there.",
    ],
  },
  {
    id: "cadence",
    title: "5. Post with cadence",
    paragraphs: [
      "Do not dump a whole pack onto one account in one sitting. One copy per account, or a small set over time.",
    ],
  },
  {
    id: "ledger",
    title: "6. Label what happened",
    paragraphs: [
      "After you post, mark the Drop Ledger.",
      "Unlabeled is unknown — not a pass, not a miss. Flagged or duplicate-rejected is a miss. A quiet week is not proof the copies worked.",
    ],
  },
  {
    id: "not",
    title: "What this is not",
    paragraphs: [
      "Studio is not checking Instagram for you.",
      "Originality in Gallery is a local check that copies are not identical to the source. It is not Instagram saying yes.",
      "Stay look-close on Fast. Do not chase a harder look just to move a number.",
    ],
  },
];

export const HOW_TO_JUMP_LINKS = [
  { href: "/", label: "Studio" },
  { href: "/gallery", label: "Gallery" },
  { href: "/settings/drive", label: "Drive" },
  { href: "/drops", label: "Drops" },
  { href: "/workflows", label: "Workflows" },
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
