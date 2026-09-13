# Agency ideas — capture 2026-09-13

Jeff: target is **agencies**. Beat TikFusion by making more of the workflow
live in **one Studio**, not by raising gate 24 or cloning Pixel AI.

This is a parking list, not a build. Lab vs Live still applies: Studio
pages ship on `varimo-live`. Engine experiments stay Lab. Do not
`git merge` the two GitHubs.

Wording: unlabeled after a drop is **`unknown`**, not a pass. How-to
talks posting hygiene + file identity. It does **not** claim Instagram
behavior.

---

## The list (do not lose)

| # | Idea | Where it lives | Note |
|---|---|---|---|
| 1 | **How-to / best practices** | Live Studio page | Already parked. Unpark next. |
| 2 | **MOV → MP4 converter** | Studio ingest | iPhone HEVC .mov is huge; TikFusion has this. ffmpeg already *opens* MOV; this is a smaller MP4 for upload/storage. |
| 3 | **Image variants** | New Studio surface | Same “one asset, many accounts” job as video. Not the video pipeline. |
| 4 | **HQ — does it actually help posted variants?** | Advice + one Lab look test | Reconstruct-first already exists. Question is look, not a new engine. Fable/Codex later. |
| 5 | **Face / body swap (trends)** | Not Generate | Trend tool, not uniqueness. Likeness/legal. Park. |
| 6 | **Cloudflare** | Already in stack | R2 is the default object store (zero egress). Also CDN/WAF/cache headers on Studio. Not a new product. |
| 7 | **Sentry** | Live Studio ops | Errors/crashes. Code is env-gated (`docs/ops/telemetry.md`). |
| 8 | **PostHog** | Live Studio ops | Product analytics (who ran Fast/HQ). Not the same as Sentry. Both. |
| 9 | **API / MCP (“connect your AI”)** | Live API keys or MCP | Generate + gallery access. Not posting as us. |
| 10 | **Repurpose.io add-on** | Scheduling add-on | Jeff already uses it. More accounts, cheaper, weak analytics. We would resell/operate a seat, not scrape IG. |
| 11 | **Buffer (or similar) add-on** | Scheduling + analytics | Official APIs, fewer accounts, more expensive, Insights. Same “we hold the sub, charge an upsell.” |
| 12 | **G-Lark cloud phones** | Integrations / far later | Jeff’s cloud phones + their API. Device farm + automation. High ToS surface. Not v1. |

---

## Rank (this studio, this year)

### Do next (Studio / Live)

1. **How-to.** Operators are already asking. Cover: drop source → Fast N → look stills → Drive → drop. File identity (SHA ≠ source, AAC never copy, no SEI). Cadence: don’t fire 20 copies at one account in one sitting. Drop Ledger: unlabeled ≠ pass. “Stay original-looking” = look-close Fast + don’t re-encode a variant as a new source. **Not** a detector guide.

2. **MOV → MP4.** Agency pain is upload size and time, not “ffmpeg can’t open .mov.” Transcode HEVC MOV → tagged H.264 MP4 (even dims, color tags) as an ingest step, then Generate as today.

3. **Turn on Sentry + PostHog keys on Live** if not already signed. They are different: Sentry = “it broke,” PostHog = “who used Fast/HQ.” Do not put keys on the Fast worker image.

### Talk, don’t build yet

4. **HQ worth it?** One Lab pair: same source, Fast vs reconstruct-first, Jeff stills + short playback. Fable/Codex get that packet, not a blank “should we GPU.” Daily pack stays Fast. HQ stays one GPU pass then Fast N.

5. **Image variants.** Real agency job. Separate recipe (no trim/speed, still SSIM/look). After How-to so Studio doesn’t grow a second engine in the same week.

6. **API / MCP.** Agencies and “connect Cursor/ChatGPT to Studio.” Scope: create job, poll, list gallery. Auth = workspace API key. No IG login, no G-Lark, no Buffer in v1 of the API.

### Add-on company (integrations talk)

This is how you become “the whole workflow” vs TikFusion’s converter+variants. It is also a **different cost and ToS shape** than a variant generator.

- **Repurpose vs Buffer:** Repurpose = more destinations / accounts per dollar, weak analytics. Buffer = official schedule + analytics, fewer accounts, higher bill. Starting small and growing the seat as agencies opt in is a real model. We do **not** scrape cookies or run unofficial posters.
- **G-Lark:** useful to Jeff personally. Offering cloud phones as an add-on is a phone farm, not a button on Generate. Park until How-to + converter + telemetry are boring.
- **Face swap:** trend content. Separate SKU or never. Do not mix into uniqueness Generate.

### Already decided / already built

| Item | Status |
|---|---|
| Cloudflare R2 | Default media store. “Wrote Cloudflare down” = this. |
| Sentry / PostHog code | Optional env; Lab first, Live after Jeff signs the week readout. |
| HQ reconstruct-first | Studio checkbox, default off. One GPU then Fast N. |
| Gate 24 / MAE 38 / vig-off | Unchanged. Not an agency idea. |
| How-to / Telegram / tone-curve | Parked on the assistant brief until this list. How-to unparks; Telegram still later; tone-curve still late-pack. |

---

## What “better than TikFusion for agencies” actually is

1. Look-close variants that still clear local 24 (the engine you already have).
2. A Studio that answers the support questions (How-to) and takes iPhone files without a 4 GB wait (converter).
3. One place for video **and later** stills.
4. Optional official posting/analytics add-on (Buffer/Repurpose seats we operate).
5. API so their VA tools and AIs can drive Generate.

Not: face-swap, cloud phones, or a built-in “stay in the green” predictor.

---

## Codex / Fable

Send **this page**, not a raw idea dump. Ask them to review rank and cuts, not to invent a roadmap. HQ question waits until we have one Fast vs HQ stills pair.
