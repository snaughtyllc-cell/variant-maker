# Agency ideas — capture 2026-09-13

Jeff: target is **OFM agencies**. The job is **one asset, many accounts**
— prepare, review, hand off a pack. “The whole workflow in one Studio”
is too loose. Adjacency does not earn a feature.

Parking list, not a build. Lab vs Live: Studio pages ship on
`varimo-live`. Engine experiments stay Lab. Do not `git merge` the two
GitHubs.

Wording: unlabeled after a drop is **`unknown`**, not a pass. How-to is
posting hygiene. It does **not** claim Instagram behavior. Do **not**
publish fingerprint internals (SHA / AAC / SEI, etc.).

Codex review (regular app, 2026-09-13) is folded in. Jeff follow-up
the same day: no internals in How-to; API is a real OFM flow; upscaler
question = HQ, not a new Fast path.

---

## The list (do not lose)

| # | Idea | Bucket | Note |
|---|---|---|---|
| 1 | **How-to / best practices** | Live Studio page | Unpark. No fingerprint internals. |
| 2 | **Ingest (MOV / iPhone files)** | Studio ingest | Only if it saves transfer/prep. HEVC→H.264 is not automatically smaller. |
| 3 | **Image variants** | Same company, later | Same job, new recipe. Needs stills volume. |
| 4 | **HQ / “upscaler”** | Quality question, not a feature | Reconstruct-first **is** the upscaler. Not 4K. Fast must not 720→1080 lanczos. |
| 5 | **Face / body swap** | **Cut from Studio** | Creative production. |
| 6 | **Cloudflare** | Infra | R2 already. |
| 7 | **Sentry** | Ops | Errors. |
| 8 | **PostHog** | Ops | Usage. |
| 9 | **API / MCP** | Live, after How-to | OFM: plug Studio into their AI + Repurpose/Buffer. Drive workflows exist; this is go-farther. |
| 10 | **Repurpose / Buffer** | Recommend as plug-ins | We do **not** operate their seats. Handoff via API. |
| 11 | **G-Lark cloud phones** | **Cut from Studio** | Device farm. |

---

## Rank

### Do next

1. **How-to (Live).** Operators already asking. Loop: drop source → Fast
   N → look stills → Drive → drop. Cadence hygiene. Unlabeled ≠ pass.
   Look-close Fast; don’t re-encode a variant as a new source. **No SHA /
   AAC / SEI / encode-tag writeup** — that’s how you get cloned. **Not**
   a detector guide.

2. **Ingest, if it actually saves transfer or prep.** “We accept MOV”
   is true today. “We save a 4 GB wait” needs convert-before-upload or a
   real bitrate shrink. Matching TikFusion’s converter name is not
   enough.

3. **API / MCP (Live).** OFM runs many accounts. We are not their
   scheduler. Pitch: Drive folder workflow is here; if you want to go
   farther, here is a key (MCP later) so *your* AI can drive Studio and
   the tools we recommend (Repurpose, Buffer, …). Scope: create job, poll,
   list gallery. No IG login. The feature existing is part of the sell.
   Ahead of image variants.

4. **Sentry on Live** (ops). PostHog when there is a usage question. No
   keys on the Fast worker image.

### Not a feature rank

- **HQ / upscaler.** Reconstruct-first is one GPU Real-ESRGAN pass, then
  Fast N, default off. That is the “this 720/1080 is muddy” lever. Fast
  **never** lanczos-upscales 720→1080 (720 snow). Cheap makers looking bad
  is usually scramble / extra encode, not missing 4K. Do not add a
  second upscaler. A Lab Fast vs HQ stills pair can say this source
  looks different; it cannot say HQ helps posted variants.

- **Cloudflare, Sentry, PostHog** as product rows.

### Same company, later — earn the slot

- **Image variants** wait on stills volume. Same job, new recipe.
- **Recommend** Buffer / Repurpose as tools that plug in via the API.
  **We hold seats and post** is a different company.

### Cut from the Studio proposition

- **G-Lark / cloud phones**
- **Face / body swap**

Out. Not “later on the same list.”

---

## Already built

| Item | Status |
|---|---|
| Cloudflare R2 | Default media store |
| Sentry / PostHog code | Optional env |
| HQ reconstruct-first | Checkbox, default off. One GPU then Fast N |
| Drive / Workflows | Inbox folder → pack. API is the next mile. |
| Gate 24 / MAE 38 / vig-off | Unchanged |
| Telegram / tone-curve | Parked. Tone-curve late-pack only |

---

## Competitive argument we will defend

A more complete **asset-pack workflow**: prepare, review, hand off.
API is how they extend that handoff. Not a phone farm, not a poster.

---

## Next build

How-to on **Live** (`varimo-live`). No fingerprint internals. Then API
handoff. Not this Lab PR.
