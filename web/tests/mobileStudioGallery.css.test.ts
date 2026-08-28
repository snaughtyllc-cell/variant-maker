import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { STUDIO_LIVE_PHONE_HEIGHT_PX, STUDIO_LIVE_RAIL_PX } from "@/lib/studioLayout";

const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
const mobile = css.split("@media (max-width: 639px)")[1] ?? "";
const desktop =
  css.split("@media (min-width: 900px)").find((part, i) => i > 0 && part.includes(".studio-live")) ?? "";

function rule(block: string, selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = block.match(new RegExp(`${escaped}\\s*\\{[^}]*\\}`));
  return match?.[0] ?? "";
}

describe("mobile Studio + Gallery CSS contract", () => {
  it("pins Generate above the phone tab bar with no white dock", () => {
    expect(mobile).toMatch(/\.studio-generate-bar--dock\s*\{[^}]*position:\s*fixed/s);
    expect(mobile).toMatch(/\.studio-generate-bar--dock\s*\{[^}]*bottom:\s*var\(--tab-h\)/s);
    expect(mobile).toMatch(/\.studio-generate-bar--dock\s*\{[^}]*background:\s*transparent/s);
  });

  it("lets the Gallery body scroll past PACKS so tiles are reachable", () => {
    expect(css).toMatch(/\.gallery-page\s*\{[^}]*overflow:\s*hidden/s);
    expect(mobile).toMatch(/\.gallery-body\s*\{[^}]*overflow-y:\s*auto/s);
    expect(mobile).toMatch(/\.gallery-grid-pane\s*\{[^}]*overflow:\s*visible/s);
    expect(mobile).toMatch(/\.gallery-packs\s*\{[^}]*flex-shrink:\s*0/s);
    expect(mobile).toMatch(/\.gallery-toolbar \.gallery-send-wrap\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.gallery-packs__search\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.gallery-grid\s*\{[^}]*minmax\(\s*80px/s);
    expect(mobile).toMatch(/\.gallery-tile\s*\{[^}]*max-width:\s*none/s);
  });

  it("keeps a single green status chip on the phone top bar", () => {
    expect(mobile).toMatch(/\.vf-topbar-left \.status-gpu\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.vf-topbar-left \.status-ready-text\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.vf-topbar-left \.status-engine\s*\{[^}]*width:\s*34px/s);
  });

  it("stacks the selection sheet: count on top, Save and Send below", () => {
    expect(mobile).toMatch(/\.gallery-floating-toolbar\s*\{[^}]*position:\s*fixed/s);
    expect(mobile).toMatch(
      /\.gallery-floating-toolbar\s*\{[^}]*grid-template-areas:\s*"count close"\s*"actions actions"/s,
    );
  });

  it("pins the Studio live/progress rail so tiles cannot eat the page", () => {
    const phoneLive = rule(mobile, ".studio-live");
    expect(phoneLive).toMatch(new RegExp(`height:\\s*${STUDIO_LIVE_PHONE_HEIGHT_PX}px`));
    expect(phoneLive).toMatch(new RegExp(`max-height:\\s*${STUDIO_LIVE_PHONE_HEIGHT_PX}px`));
    expect(phoneLive).toMatch(/overflow:\s*hidden/);
    expect(phoneLive).not.toMatch(/max-height:\s*none/);
    expect(phoneLive).not.toMatch(/height:\s*auto/);
    expect(rule(mobile, ".studio-live__finished")).toMatch(/overflow-y:\s*auto/);

    const deskLive = rule(desktop, ".studio-live");
    expect(deskLive).toMatch(new RegExp(`flex:\\s*0 0 ${STUDIO_LIVE_RAIL_PX}px`));
    expect(deskLive).toMatch(new RegExp(`width:\\s*${STUDIO_LIVE_RAIL_PX}px`));
    expect(deskLive).not.toMatch(/flex:\s*1 1 auto/);
  });

  it("keeps the full varimo wordmark in the phone top bar", () => {
    expect(mobile).toMatch(/\.vf-brand-wordmark\s*\{[^}]*display:\s*inline-block/s);
    expect(mobile).toMatch(/\.vf-brand-mark\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.vf-more-trigger\s*\{[^}]*font-size:\s*0/s);
  });
});
