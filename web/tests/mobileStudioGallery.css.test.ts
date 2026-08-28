import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(__dirname, "../app/globals.css"), "utf8");
const mobile = css.split("@media (max-width: 639px)")[1] ?? "";

describe("mobile Studio + Gallery CSS contract", () => {
  it("pins Generate above the phone tab bar", () => {
    expect(mobile).toMatch(/\.studio-generate-bar--dock\s*\{[^}]*position:\s*fixed/s);
    expect(mobile).toMatch(/\.studio-generate-bar--dock\s*\{[^}]*bottom:\s*var\(--tab-h\)/s);
  });

  it("lets the Gallery body scroll past PACKS so tiles are reachable", () => {
    expect(css).toMatch(/\.gallery-page\s*\{[^}]*overflow:\s*hidden/s);
    expect(mobile).toMatch(/\.gallery-body\s*\{[^}]*overflow-y:\s*auto/s);
    expect(mobile).toMatch(/\.gallery-grid-pane\s*\{[^}]*overflow:\s*visible/s);
    expect(mobile).toMatch(/\.gallery-packs\s*\{[^}]*flex-shrink:\s*0/s);
    expect(mobile).toMatch(/\.gallery-toolbar \.gallery-send-wrap\s*\{[^}]*display:\s*none/s);
  });

  it("stacks the selection sheet: count on top, Save and Send below", () => {
    expect(mobile).toMatch(/\.gallery-floating-toolbar\s*\{[^}]*position:\s*fixed/s);
    expect(mobile).toMatch(
      /\.gallery-floating-toolbar\s*\{[^}]*grid-template-areas:\s*"count close"\s*"actions actions"/s,
    );
  });

  it("keeps the full varimo wordmark in the phone top bar", () => {
    expect(mobile).toMatch(/\.vf-brand-wordmark\s*\{[^}]*display:\s*inline-block/s);
    expect(mobile).toMatch(/\.vf-brand-mark\s*\{[^}]*display:\s*none/s);
    expect(mobile).toMatch(/\.vf-more-trigger\s*\{[^}]*font-size:\s*0/s);
  });
});
