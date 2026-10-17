/**
 * varimo echo mark — overlapping "o" rings, one accent fading outward.
 *
 * Colour comes from `currentColor`, so the mark takes the Studio aqua from its
 * container (`.vf-brand-mark`, `.login-brand-mark`) rather than introducing a
 * colour of its own. The canonical brand artwork in `/brand` keeps the brand
 * violet; Studio tints it to `#16c8d3`.
 *
 * Brand rule: the three-echo mark muddies below 32px, so smaller sizes render
 * the two-ring simplification (see `brand/source/varimo-favicon.svg`).
 */

type Ring = { cx: number; r: number; width: number; opacity: number };

const ECHO_RINGS: Ring[] = [
  { cx: 23, r: 14, width: 6.5, opacity: 1 },
  { cx: 33, r: 14, width: 6.5, opacity: 0.45 },
  { cx: 43, r: 14, width: 6.5, opacity: 0.18 },
];

const COMPACT_RINGS: Ring[] = [
  { cx: 26, r: 15, width: 11, opacity: 1 },
  { cx: 42, r: 15, width: 11, opacity: 0.4 },
];

export function VarimoMark({
  size = 24,
  className,
}: {
  size?: number;
  className?: string;
}) {
  const rings = size < 32 ? COMPACT_RINGS : ECHO_RINGS;
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {rings.map((ring) => (
        <circle
          key={ring.cx}
          cx={ring.cx}
          cy={32}
          r={ring.r}
          fill="none"
          stroke="currentColor"
          strokeWidth={ring.width}
          opacity={ring.opacity}
        />
      ))}
    </svg>
  );
}
