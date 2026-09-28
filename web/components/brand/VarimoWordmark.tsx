/**
 * varimo wordmark — "varim", the accent "o", and its fading echoes.
 *
 * Set in the brand typeface at the brand's -4% tracking, with each echo stepped
 * 0.538em so the o's overlap exactly as they do in `brand/wordmark.svg`. The word takes `currentColor`; the accent and
 * echoes take the Studio aqua.
 *
 * Brand rule on minimum sizes: the four-echo lockup needs ~120px of width, two
 * echoes hold down to 80px, and below that the mark replaces it (`VarimoMark`).
 */

const ECHO_OPACITY = [0.5, 0.24, 0.1] as const;

export function VarimoWordmark({
  echoes = 3,
  className,
}: {
  echoes?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <span className={className ? `varimo-wordmark ${className}` : "varimo-wordmark"}>
      varim<span className="varimo-wordmark__accent">o</span>
      <span className="varimo-wordmark__echoes" aria-hidden="true">
        {ECHO_OPACITY.slice(0, echoes).map((opacity, i) => (
          <span key={i} style={{ opacity }}>
            o
          </span>
        ))}
      </span>
    </span>
  );
}
