# Butter loop → VaryForge (flow, not a clone)

**Date:** 2026-08-20  
**Status:** North star for “no-brainer” product — do not clone Butter  
**Product name:** VaryForge  
**Reference:** [hellobutter.io](https://hellobutter.io/) (Jeff, 2026-08-20)

Butter’s pitch is one loop: **Post → Track → Amplify → Repeat.** Upload once,
distribute to every account, see what performs, mint more variants of winners.
Agencies buy that *flow*, not a pile of folders.

VaryForge already owns the hard part they market as “repurpose”: **real unique
variants** (color-correct Fast, uniqueness gate, VMAF). Butter’s engine is
hooks / grades / overlays on the same clip. We do not copy that look. We do
not become their poster, marketplace, or IG login farm.

The no-brainer is: **their loop, our uniqueness, our Studio as the one place
it happens.**

## How we beat them (not by becoming Butter)

They win today on **glue**: one screen from library → post → numbers → more
variants. Their “variants” are the weak link (overlays / hooks / grades on
the same file). Upload-time duplicate is exactly the miss Jeff’s VAs feel.

We win if an agency believes three things at once:

1. **These files get on the platform.** Color-correct Fast, VMAF floor,
   uniqueness gate — not a sticker pack. That is the spoof they cannot
   buy from Butter without looking cheap or getting duplicate-rejected.
2. **I never leave Studio to run the week.** Drops board + split to
   account folders + generate-more on winners. Drive / Repurpose (or the
   phone) still *publishes*. We do not log into 50 Instagrams.
3. **It is faster to say yes than to run Butter + a spoofer.** Phone save
   without ZIP, Connect Google as *their* Drive, Team for their VA.
   Two tools is the competitor. One URL is us.

Do **not** try to beat them at native posting, CPM dashboards, shoutout
marketplaces, or overlay volume. That is their product and their risk
(account farms, real-device posting). Our customer already has VAs and
Repurpose. They need files that survive, and a loop that does not live in
Sheets.

**Kill shot:** Butter is a poster that mints lookalikes. VaryForge is a
variant engine that learned to feel like a poster. When Drops + amplify
ship, they do not need both.

## Butter’s five steps (what “flow” means)

From their site (not our backlog):

| # | Butter | What the operator feels |
|---|---|---|
| 1 | Library by account / platform | Clips live in one place, not Drive + Notion + three schedulers |
| 2 | Repurpose engine | 1 clip → many posts that don’t look like copies |
| 3 | Posting module | Queued to every account, daily goals, team roles |
| 4 | Analytics | Views / CPM / engagement per account in one dashboard |
| 5 | Amplify | Winners automatically get more variants |

“Organized by client. Editors upload. You approve. Clients only see theirs.”
That’s workspaces + Team, which we just shipped.

## What we already have (wire these; don’t rebuild)

| Butter feeling | VaryForge today |
|---|---|
| Client workspace | Invite-only **workspace** + Admin Open |
| Editors vs owner | **Team** owner / member |
| 1 clip → many unique posts | **Generate Fast 20** (uniqueness 24-bit, not overlays) |
| Split across accounts | **Pack split** to main / trial / growth Drive folders |
| Captions | Caption banks (niche), not Butter text overlays |
| Inbox automation | **Workflows** (Drive in → generate → out) |
| “Did it land?” | Gallery **Passed / Duplicate / Flagged** + Drop Ledger 12a |
| Library | Gallery + Drive destinations |

The gap is not “make variants.” It’s that those pieces still feel like
**separate rooms**. Butter wins because the next step is on the same screen.

## What we will not copy

`CLAUDE.md` / farm scope: no account proxies, no logging into 50 Instagrams
from Studio, no “real-device posting,” no mass DMs, no unban marketplace.

| Butter module | VaryForge stance |
|---|---|
| Native TikTok / IG / YT / X posting | **Out.** Repurpose (or the VA’s phone) stays the poster. |
| Official CPM / views APIs | **Later / optional.** No scrape. Unlabeled = pass until someone labels. |
| Overlay / hook scramble | **Out.** That’s the cheap look. Our variants stay real. |
| Shoutout / live / unban marketplace | **Out.** Not this product. |
| Auto-queue 100 overlay variants of winners | **No overlays.** “Generate more of this source” is allowed. |

If an operator wants Butter’s poster, they can keep Butter for posting and
use VaryForge for uniqueness. Our job is to make **staying in Studio** good
enough that they don’t need two brains.

## The VaryForge loop (same story, our plumbing)

```
Source (phone / Drive inbox)
  → Generate Fast (unique variants, quality on)
  → Split / Send to Drive  (one folder = one account / Repurpose queue)
  → VA posts from that folder
  → Drops board: unlabeled = pass; flag / duplicate if the platform said so
  → Amplify: “more like this” on winners (same source, new seeds) — not overlays
```

That is Post → Track → Amplify without logging into Instagram.

## Build slices (flow, in order)

### F0 — Paste the live post link (ship with Studio)

VAs post from Drive / the phone / Repurpose, then **paste the permalink**
onto the variant in Gallery. Studio stores `post_url` (not Drive `drop_url`),
opens it in one click, and later can attach views if a *public* lookup or
official API exists. Age-gated 18+ accounts will not scrape without a
logged-in browser — we do not run that farm.

See `docs/superpowers/specs/2026-08-20-post-url-tracking.md`.

### F1 — Drops board in Studio (the missing room)

One **Drops** view (nav slot Diagnostics vacated for operators):

- Rows: source, date, destination (main/trial/growth), how many sent
- Per variant: unlabeled = pass, duplicate, flagged
- Filter: this week / misses only
- Same labels as Gallery; Drop Ledger stays the durable sheet

Identity: `job_id` + variant id. After 12b, Drive file id (Repurpose rename).

**Box:** new `web/app/drops/` (or Gallery filter), export-job reads, Drop Ledger
status. Not sampler, not RunPod, not Butter-like posting.

### F2 — Generate → accounts on one rail

After a Fast pack: the next click is **split to destinations**, not “remember
the Drive page.” Surface pack-split on the completed job / Gallery, with the
three account folders they already saved.

Daily **goal** can be a number on the workflow (already have count) plus a
small “posted today” from Drops — not a native poster.

### F3 — Amplify winners (12c, mild)

“This source passed everywhere → Generate N more.” Uses the same Fast engine
and uniqueness gate. Feed **flagged** recipes the other way (don’t clone
losers). Still not a detector.

### F4 — Optional live metrics (only with a real API or public lookup)

v1 already stores `post_url`. If a platform gives us views on *our*
connected account later, attach them to that URL. Public oEmbed is optional
and will miss 18+ / restricted posts. Do not scrape logged-in Instagram.

## Success

An agency can sit in one Studio URL: drop a clip, get unique files, send
main/trial/growth, see what got flagged, hit generate-more on a winner —
without Google Cloud, without Jeff’s Gmail on a folder, without a ZIP on
the phone, without opening Butter to understand the week.

## Frozen

24-bit Fast gate, VMAF on, Fast = CPU, HQ = GPU, unlabeled = pass,
invite-only, no Pixel-AI overlays, no account-proxy posting.
