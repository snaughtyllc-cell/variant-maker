# Agency ideas — capture 2026-09-13

Jeff: target is **agencies**. The job is **one asset, many accounts** —
prepare, review, hand off a pack. “The whole workflow in one Studio” is
too loose; it can justify a converter, a scheduler, or a phone farm.
Adjacency does not earn a feature.

Parking list, not a build. Lab vs Live: Studio pages ship on
`varimo-live`. Engine experiments stay Lab. Do not `git merge` the two
GitHubs.

Wording: unlabeled after a drop is **`unknown`**, not a pass. How-to is
posting hygiene. It does **not** claim Instagram behavior.

Codex review (regular app, 2026-09-13) is folded in below.

---

## The list (do not lose)

| # | Idea | Bucket | Note |
|---|---|---|---|
| 1 | **How-to / best practices** | Live Studio page | Unpark. Operators already asking. |
| 2 | **Ingest (MOV / iPhone files)** | Studio ingest | Pain is transfer/prep, not “ffmpeg can’t open MOV.” HEVC→H.264 is not automatically smaller. |
| 3 | **Image variants** | Same company, later | Same job, new recipe. Needs stills volume, not “after How-to.” |
| 4 | **HQ look question** | Quality question, not a feature | Reconstruct-first exists. Fast vs HQ stills ≠ “helps posted variants.” |
| 5 | **Face / body swap** | **Cut from Studio** | Creative production, not asset-pack. |
| 6 | **Cloudflare** | Infra | R2 already. Not a feature rank. |
| 7 | **Sentry** | Ops | Errors. Env-gated. Not a product bet. |
| 8 | **PostHog** | Ops | Usage. Different from Sentry. Turn on when there is a question to measure. |
| 9 | **API / MCP** | Live, if batch demand | Generate + gallery. “Connect your AI” is packaging. Recurring batches would pull this ahead of images. |
| 10 | **Repurpose.io add-on** | Boundary: handoff vs we-operate-seats | More accounts, cheaper, weak analytics. |
| 11 | **Buffer add-on** | Same boundary | Official schedule + Insights, fewer accounts, costlier. |
| 12 | **G-Lark cloud phones** | **Cut from Studio** | Distribution infrastructure / device farm. |

---

## Rank

### Do next

1. **How-to (Live).** Demand is already here. Cover the loop you already
   sell: drop source → Fast N → look stills → Drive → drop. Cadence is
   hygiene (don’t dump 20 copies on one account in one sitting). Drop
   Ledger: unlabeled ≠ pass. “Stay original-looking” = look-close Fast +
   don’t re-encode a variant as a new source. SHA / AAC / SEI belong in
   a short “what’s in the file” note, not the product promise. **Not** a
   detector guide.

2. **Ingest, if it actually saves transfer or prep.** “We accept MOV”
   (true today) and “we save a 4 GB wait” are different claims. Converting
   *after* upload does not remove the upload. HEVC is often *smaller*
   than H.264 at the same quality; a converter that only remuxes or
   transcodes to H.264 can make files bigger. Rank this only if we
   shrink bitrate, convert **before** upload, or fix a real
   compatibility/tooling mess. Matching TikFusion’s feature name is
   not enough.

3. **Sentry on Live** (ops). Crashes while agencies are on the box.
   PostHog when there is a usage question worth measuring. Not a
   feature slot. No keys on the Fast worker image.

### Not a feature rank

- **HQ.** One Lab Fast vs reconstruct-first stills pair can say “this
  source looks different.” It cannot say HQ helps posted variants. Daily
  pack stays Fast. Tone-curve stays late-pack / fail-24.

- **Cloudflare, Sentry, PostHog** as product rows. Infra / ops.

### Same company, later — earn the slot

- **API** before **image variants** only if agencies are asking to
  automate repeat Generate. Otherwise How-to + ingest first; images
  wait on stills volume, not calendar. Image variants are this job
  (one still, many accounts) but a new recipe is a real expansion.
- **Scheduler handoff** (export / “open in Buffer”) extends the Studio.
  **We hold Buffer/Repurpose seats and post for them** is a managed
  distribution company: accounts, billing, support, posting failures.
  Official APIs do not settle that it is *this* business. Wait until
  agencies show handoff—not prep—is the obstacle.

### Cut from the Studio proposition

- **G-Lark / cloud phones** — operating distribution infrastructure.
- **Face / body swap** — creative production / likeness.

Not “later on the same list.” Out.

---

## Already built

| Item | Status |
|---|---|
| Cloudflare R2 | Default media store |
| Sentry / PostHog code | Optional env; Live after Jeff signs |
| HQ reconstruct-first | Checkbox, default off. One GPU then Fast N |
| Gate 24 / MAE 38 / vig-off | Unchanged |
| Telegram / tone-curve | Still parked. Tone-curve late-pack only |

---

## Competitive argument we will defend

A more complete **asset-pack workflow**: prepare, review, hand off.
Not accumulating adjacent services under “one Studio.”

---

## Next build

How-to on **Live** (`varimo-live`). Not this Lab PR.
