# After the sales tracks — what we build next

**Date:** 2026-08-20  
**Status:** Plan — do not start these until A/B/C are in operators’ hands  
**Product name:** VaryForge  
**Depends on:** `2026-08-20-sales-tracks.md` (A Team, B Drop Ledger 12a, C onboarding)

This is the order **after** the current slice. Triggers, not calendars. First
paying operators run on **isolated studios + Team + Fast 20 + Drive**. Hardware
and billing wait until a real queue or a real invoice pain shows up.

## What “this is all done” means

| Track | Done when |
|---|---|
| **A Team** | A new-workspace owner invites their VA on `/team` without Jeff. Shipped on Studio PR. |
| **B Drop Ledger 12a** | Drive page has Ensure / Sync / open sheet. Gallery can mark Flagged. Unlabeled = pass. |
| **C Onboarding** | Short ops page: Connect Drive, Team, Fast vs HQ, workflow vs one-off. |
| **D Hybrid runners** | Still parked until the trigger below. Not part of “sales slice done.” |

Sell on that. Then upgrade capacity. Do not wait for Stripe or a bigger GPU
to take the first outside operator.

## Frozen for every later wave

- Color correctness, zero-mean color, VMAF floor, audio sync.
- Fast uniqueness **24 vs source / 24 vs peers** (~38% UI pass). Medium should
  *score* ~55–65% on talking-head. Do not raise the gate to 55% / 32 bits.
- Escalate stays on. Do not skip the quality guard.
- Fast = CPU libx264. HQ = GPU reconstructive. Do not split **one pack** across both.
- Min workers stay **0** unless we explicitly buy a warm Fast CPU window.
- Not a detector. Not Pixel AI / Telegram-bot clones.
- Invite-only until billing is the actual bottleneck. No public signup, no Postgres
  until the JSON tenant file hurts.

---

## Wave 1 — two studios generating at once (unpark D)

**Trigger:** A second workspace is waiting on Fast while another is mid-job.
Until then one Fast CPU endpoint is enough.

**Build:** Occupancy routing. If workspace A holds a live Fast job, boot a
**second serverless Fast CPU** for workspace B. If only one studio is busy,
they keep the single worker (no extra spend). Same idea later for a second
HQ GPU — not in this wave.

**Not:** dedicated card per customer, always-on GPU, serializing Fast into
one line, uniqueness changes.

**Files (when unparked):** `runpod_runner.py`, `runner.py`, Fast endpoint env,
`docs/ops/railway-studio.md`. Spec notes already live on the workspaces doc
(`Later — hybrid runners`) and sales-tracks Track D.

This is how we take a third agency without one giant shared queue.

## Wave 2 — interactive 1–2 clip wait

**Trigger:** A real operator (or Jeff) is blocked on Studio Generate for
**one or two files**, not on Drive workflows. Workflow pull → generate → send
can stay slow.

**First:** measure. Warm vs cold Fast start, time-to-first-variant, time for
count=1 vs count=8 vs count=20. Optional: Jeff sends a Telegram-spoofer
sample so we can probe resolution/filters/whether it skipped VMAF — **probe,
don’t clone**.

**Then, in order:**

1. Ops: FlashBoot, idle timeout ~10 min, morning 1–3 Fast primer so the CPU
   is warm. No code if that closes the gap.
2. Code only if still slow: more Fast parallelism on the existing worker,
   or a **business-hours warm Fast CPU** (cost trade, still not a 4090).
3. Still later: always-on Fast CPU if the primer + hybrid still leave a
   cold-start hole. Always-on **GPU** stays off.

**Not:** turning escalate off, uniqueness 55%, HQ for the daily 1–2 clip,
Railway 20-packs.

## Wave 3 — HQ capacity when Fast is no longer the queue

**Trigger:** More than one workspace wants HQ at the same time, or HQ hits
the RunPod time cap on a real pack.

**Build:** Second HQ endpoint with the same occupancy rule as Wave 1
(busy studio → idle GPU boots; idle overnight → $0). Ops may also mean a
**better GPU class** on the existing HQ endpoint (still min workers 0,
longer execution timeout). That is an env/card change, not a product rewrite.

HQ stays serial per worker. Do not expect a 20 HQ pack in a few minutes from
card class alone.

## Wave 4 — tracking that survives Repurpose (Phase 12b)

**Trigger:** 12a is in use and a flagged file cannot be found because
Repurpose renamed it to the caption.

**Build:** On Send to Drive success, write **Drive file id** (`drop_url`) onto
the ledger row. Identity is `job_id` + `variant_id`, then Drive id — never
the caption filename. Optional: short id prefix on the file we upload.

Spec: `2026-08-18-platform-outcome-learning.md` §12b. Still not a detector.

## Wave 5 — learn from real misses (Phase 12c)

**Trigger:** Enough explicit `flagged` / `duplicate_reject` rows to change a
preset without guessing. Unlabeled still counts as pass.

**Build:** Read those rows (Sheet is fine) and bias uniqueness / preset /
auto-tune **mildly**. Export flagged recipes (seed, strength, uniqueness).
A DB only if Sheets is the bottleneck.

**Not:** an on-box “will IG catch this” model. That stays a **separate
project** (`CLAUDE.md`).

## Wave 6 — money and self-serve (last on purpose)

**Trigger:** Jeff is the bottleneck for `new_workspace` invites **and**
money is changing hands often enough that a spreadsheet of operators hurts.

**Then, in order:**

1. Copy-link invite + workspace rename (still invite-only, still JSON tenants).
2. Light usage readout for Jeff (who ran Fast/HQ, when) so hybrid spend is
   visible before Stripe.
3. Stripe + plan limits **after** that. Postgres when `tenants.json` is
   actually painful (many operators, concurrent writes). Public signup only
   with a paid gate — not an open Studio.

**Not in this wave:** per-VA Drive inside Jeff’s own workspace (VAs there
share packs on purpose). Owner workspaces already have their own Drive.

---

## Nice-to-haves (only if a wave above is idle)

- Invite email send (today: tell them the URL + email). Not required to sell.
- Member vs owner vs a later “manager” role. Owner + member is enough for a
  VA.
- Path-B ~35% similarity readout as a **display**, not a raised Fast gate.
- RIFE in the HQ worker image (interpolation exists in code; binary may not
  be in the GPU image yet).
- **In-app announcements** (Jeff 2026-08-29): a place in Studio where
  operators see updates and bug fixes (captions model, Save-to-phone,
  etc.) without a Slack/email. Not a tab this week. Not a changelog
  page that redesigns invent early. Note only:
  `docs/ops/studio-ia.md` → Later.
- **Instagram Analytics** (Jeff 2026-09-02): official Meta Connect (many
  tester accounts) → Analytics scoreboard + Gallery compact views → amplify
  winners. Product track, not a capacity wave. Can run in parallel with
  Waves 1–3 the same way butter-loop can. Spec:
  `docs/superpowers/specs/2026-09-02-instagram-insights-gallery.md`.
  Ops: `docs/ops/instagram-testers.md`. Do not mash into Phase 12c
  (policy labels ≠ view counts).

## Explicitly later / never for this product

| Idea | Why it waits |
|---|---|
| Local IG/TikTok detector | Separate project. Platform is the oracle. |
| Uniqueness 55% / 32-bit Fast gate | Escalated whole 20-packs. Floor stays 24. |
| Clone Telegram spoofer / Pixel AI | Probe a sample if offered; don’t copy the recipe. |
| Split one Fast pack across CPU+GPU | Two uniqueness states, two cancel paths. |
| Always-on GPU | ~$24/day for idle 4090. Warm Fast CPU is the cheaper lever. |
| Redis / desktop app / account proxies | Out of `CLAUDE.md` scope. |

## How to pick the next agent after A/B/C land

1. If a second studio is queued on Fast → **Wave 1 (D)**.
2. Else if 1–2 clip Generate is the complaint → **Wave 2** (measure first).
3. Else if flagged files vanish after rename → **Wave 4 (12b)**.
4. Else if Jeff is drowning in invites/invoices → **Wave 6**, still
   invite-only until Stripe exists.
5. Else if pack scoreboard is the complaint (open 20 Reels to see which
   original won) → **Instagram Analytics** spec (G1 Connect first).
6. Do not start 12c, Stripe, Insights auto-amplify, and hybrid runners in
   the same week — they share almost no files, but they compete for “what
   is the product.”

Operator-friction (Diagnostics hide, Drive trust, phone save-without-zip,
drops board) is `docs/superpowers/specs/2026-08-20-operator-friction.md`.
Butter-style **flow** (Post → Track → Amplify in Studio, not a poster clone)
is `docs/superpowers/specs/2026-08-20-butter-loop.md`. Those can run in
parallel with capacity waves; they do not raise uniqueness.
