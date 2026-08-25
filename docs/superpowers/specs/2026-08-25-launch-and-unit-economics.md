# Launch: test reels, unit economics, plans, uniqueness loop, DIFM

**Date:** 2026-08-25  
**Status:** Active — Jeff + homie pushing test reels / first operators soon  
**Product:** VaryForge  
**Live Studio:** https://varyforge-studio-production.up.railway.app  
**Depends on:** shipped Team / Drive / Drops / Workflows, Fast pin `856e23d` on `j0b1q4iuunzhnq`

This is the working brief for **getting people on the tool** without waiting
for Stripe, and for **pricing from real COGS** so a 10-source × 20-copy month
has a known margin. It also parks the uniqueness research agent on **lab Fast
only**, and names the later **do-it-for-you** posting service.

## What we are selling (say this out loud)

Not “unlimited AI spoof.” Not TikFusion overlays. Not a poster that logs into
50 Instagrams.

**DIY:** Unique, color-correct Fast packs that survive upload, from a phone,
in one Studio URL.

**Later DIFM:** Same files, plus a VaryForge VA who drips them with a posting
strategy (not dump-20-today).

Butter/TikFusion stay in the market by shipping every week. We match that
**cadence on uniqueness + look** (lab loop, Jeff signs) — not by cloning
Pixel AI.

## Frozen (still true while we sell)

- Gate **24/24** (~38% UI). Do not raise `TARGET_BITS`.
- Fast never face-protects. Color zero-mean. Audio sync. Even dims.
- Live Fast stays digest-pinned, **no `VF_LAB`**. Experiments → lab
  `xar25v77v3j27u`.
- Not a detector. Platform is the oracle. Unlabeled after a drop = pass.
- Invite-only until money-in is the bottleneck. No public signup this week.
- Do not split one pack across Fast and HQ.

---

## 1. What a generation actually costs

RunPod bills **per second the worker is up**, not per variant. You pay:

1. **Start** (FlashBoot ~sub-second to a few seconds if the snapshot is warm;
   true cold can be tens of seconds).
2. **Encode + uniqueness + VMAF** for every copy.
3. **Idle timeout after the last job on that worker** — live Fast is **600s
   (10 min)**. That 10 min is billed even if nobody is generating. It is why
   the next Generate feels instant.

Live Fast: `cpu3g-8-32` (8 vCPU / 32 GB), min workers **0**, max **2**,
FlashBoot on. HQ: 4090-class GPU endpoint `f0carwe6u9bdd6`, same idle 600s,
min 0.

**Rate to plug in (confirm on the next RunPod invoice / endpoint UI):**

| Worker | Planning band | Why a band |
|---|---|---|
| Fast CPU `cpu3g-8-32` | **~$0.40 / worker-hour** (invoice still TBD) | Public CPU formula ≈ `$0.01667/vCPU/hr + $0.00833/GB RAM/hr` → 8+32 ≈ **$0.40/hr**. Old $0.25–$0.45 band; use $0.40 until the invoice line for `varyforge-fast-cpu` says otherwise. |
| HQ 4090-class serverless | **~$0.40–$0.70 / worker-hour** | Same: per-second flex. Idle 10 min after HQ is the expensive surprise. |
| Railway Studio + volume | **~$20–60 / month** shared | All workspaces share one URL. Do not allocate this 1:1 to one tester. |
| Object storage | **near $0** at 24h gallery TTL | Packs expire; R2 is a mailbox, not a film archive. |

### Timed pack — live Fast 20, 2026-08-25 (this is the quote)

Ran on live `j0b1q4iuunzhnq` (`varyforge-fast-cpu`), same digest as production,
**no `VF_LAB`**, no live PATCH. Clip: `portrait.mp4`, **720×1280, 22.06s,
30fps** (daily-SKU talking-head, not the 2s fixture). Count **20**,
`quality_mode=fast`, `jobs=8`, `allow_creative_escalate=true`, autotune on
(max 5 strength iters then one strong escalate). Workers were **already
warm** (2 idle / 2 ready). Job id `3e79485c-ba95-47df-9987-6d2d6aa5de37-u2`,
worker `mu4rioyvxk8vi6`. Raw timeline: `docs/ops/fast-20-timing-2026-08-25.md`.

| Field | Measured |
|---|---|
| Queue / pickup | `delayTime` **842 ms** (warm) |
| Worker start → terminal | `executionTime` **3,612,120 ms** (**60.2 min**) |
| Studio done / R2 copy-back | **n/a** — job never returned a result |
| Requested vs delivered | **20 requested, 0 returned** |
| On-worker progress | copies **1–8 `done` at ~24.9 min**; **9–16** still uniqueness after escalate at timeout; **17–20 never started** |
| Terminal | **`FAILED` / `executionTimeout exceeded`** (endpoint cap **3600s**) |
| Idle after this job | live **600s**; a second Fast CPU was already idle at submit (max 2 occupancy, not this pack’s encode) |
| Cold-start TTFV | **not measured** (this run was warm) |

Every copy that ran took the **pessimistic uniqueness path**: 5 autotune
renders + 1 creative escalate (6 encodes). None of 1–8 cleared the 24-bit
gate on autotune; they only reached `done` after escalate. Copies 9–16
followed the same ladder; uniqueness-vs-peers after wave 1 was slower
(~160s dwell vs ~14s on wave 1), so wave 2 was still scoring the escalate
encode when the 3600s cap hit.

First encode wave of 8 was **~3 min** (render → checking at ~180s). If this
clip had cleared uniqueness on iter 1, a 20-pack would have been ~3 waves
× ~3–4 min ≈ **10–15 min** — the old planning band. **This talking-head did
not take that path.**

| Clip | Copies | What happened | Worker time | + 10 min idle |
|---|---|---|---|---|
| 22s 720 talking-head Fast (this run) | 20 | **timeout, 0 delivered** | **60.2 min billed encode** | +10 min |
| Same clip, first 8 that reached `done` | 8 | success on-worker, not returned | **~24.9 min** | +10 min |
| Same × 10 sources as 10 Fast **8**s (1 worker, sequential) | 80 | extrapolated from wave 1 | **~4.15 h encode** | +10 min once if batched |
| Same × 10 sources as 10 Fast **20**s | 200 | **does not complete** inside 3600s today | ~$0.40 encode **wasted per timeout** | +10 min each |

### Worked example — 10 sources × 20 Fast copies (the question)

**Do not quote the old ~$1 / 200-files number for this SKU.** A 20-pack of
this 22s 720 talking-head does not finish on live Fast. Each timeout still
bills ~60 min encode + 10 min idle:

| Piece | Time | Cost at $0.40/hr |
|---|---|---|
| One failed Fast 20 (this run) | 1.00 h encode | **$0.40** |
| Cooldown if last job on that worker | 0.17 h | **$0.07** |
| **COGS for 0 gallery files** | | **~$0.47** |
| Ten such clicks (10×20 month, all timeout) | 10 × (1.00 + 0.17) h | **~$4.70** and **no files** |

**Path that actually delivers today — Fast 8 of this clip:**

| Piece | Time | Cost at $0.40/hr |
|---|---|---|
| Encode 8 (measured wave 1) | 0.415 h | **$0.17** |
| One cooldown | 0.17 h | **$0.07** |
| **COGS compute / source** | | **~$0.23** for 8 files |
| 10 sources × Fast 8, one worker, sequential, one cooldown | 4.15 + 0.17 h | **~$1.73** for 80 files |
| 25 × Fast 8 to hit Creator’s 200-copy month | 10.4 + idle | **~$4.1–$5.8** depending on how many cooldowns |

If they fire 10 separate Generates hours apart: extra **~9 × 10 min idle**.
Product rule is still **batch in one Generate** — but batching a Fast 20 of
this clip currently **fails**, so the first-tester rule is **Fast 8**, not
“then Fast 20.”

Per-variant COGS on a **successful Fast 8** of this clip: **~$0.03**
($0.23 / 8), not $0.005. Escalate ate the cheap band.

HQ is **not** this math. A 20 HQ pack can sit on a 4090 for a long time; do
not sell HQ as the daily 20. HQ is the upsell / hard talking-head.

### What this means for live (do not PATCH Fast from this)

- **Do not raise `TARGET_BITS` / the 24/24 gate** to buy a faster pack.
- **Do not raise live execution timeout** from this doc alone — Jeff signs
  ops. A completing 20 on this uniqueness path would need **~75–90 min**
  (wave 2 was ~10 min slower than wave 1; copies 17–20 never started).
- Lab uniqueness loop is how we make iter-1 clears more common. Until then,
  testers stay on **Fast 8**.
- Cold-start time-to-first-variant is still unmeasured.

### Margin (use the timed pack)

Sell **the month**, not the second. $99 is still a fine DIY placeholder **if
they get files**. Compute on Fast 8 is still cheap vs $99. The new risk is
**paying ~$0.47 for a Fast 20 that returns nothing.**

| If they pay | For a month of Fast **8**s (80–200 files) | Gross vs ~$2–6 COGS |
|---|---|---|
| $49 | test / creator | still ~8–25× |
| $99 | default DIY | still ~15–50× |
| $149 | comfortable DIY | still ~25–75× |

The old “~80× on $1.20 COGS” assumed a 15 min Fast 20 that delivered 20.
That pack **did not exist** on this clip.

**What eats margin:** uniqueness autotune + escalate (this run: 6 encodes
per copy), Fast 20 timeouts, HQ, two agencies generating at once (second
Fast worker), idle 10 min on sparse clicks, and **VA time** on DIFM.

Do not price DIY at TikFusion “unlimited” until max workers and quotas exist.
Two concurrent packs = two Fast CPUs billed in parallel.

---

## 2. Plans — tabs and limits (not all rooms on day one)

The live IA has nine destinations. Testers should not see a control-plane.
**Gate extras by plan**, even while invite-only (Jeff sets the plan on the
workspace). Stripe later copies the same flags.

| | **Creator (DIY)** | **Pro** | **Agency** | **Internal / Jeff** |
|---|---|---|---|---|
| **Who** | One person, test reels | Small team, self-post | Managers + VAs | Us |
| **Studio / Gallery / Drive** | yes | yes | yes | yes |
| **Drops** | yes (they must label) | yes | yes | yes |
| **Workflows** | no (or later) | yes | yes | yes |
| **Team** | no | yes (invite VAs) | yes | yes |
| **Admin / Diagnostics** | no | no | no | site admin only |
| **Quota (Fast)** | **10 sources × 20 copies / 30 days** = 200 | 50 × 20 = 1,000 | 150 × 20 = 3,000 | uncapped |
| **HQ** | off or 1–2 clips | small cap | cap | uncapped |
| **Seats** | 1 | 3 | 10 | — |

Creator quota **is** the 10×20 example. If a tester only needs 8 copies,
they still spend the same worker-time per copy; the cap is on **delivered
ok variants**, not “Generate clicks.”

First testers: Jeff invites, plan=`creator`, cap=200. No Stripe. Soft
block in Studio: “You’ve used 180 / 200 this month.”

**Do not ship public signup** to make this feel real. Invite + cap is enough
to start test reels this week.

---

## 3. First people on the tool (this week, not after billing)

Order:

1. **Invite-only workspaces** (already live). One URL. Their Drive, their
   gallery.
2. **Phone path that actually posts:** Studio drop → Fast 8 (not 20) on the
   first reel → Gallery Share/Save without ZIP → they post → they mark
   Drops (unlabeled = pass).
3. **Do not** graduate them to Fast 20 of 22s 720 talking-head until a pack
   of that SKU returns files (timed 20 timed out). Stay on Fast 8.
4. **Quota cap** in `tenants.json` before the third tester, so one person
   cannot sit on both Fast workers for a weekend.
5. Stripe / self-serve only when Jeff is the invite bottleneck **and** money
   is repeating (`after-sales-tracks` Wave 6).

Onboarding copy they need on-screen, not a PDF:

- Fast vs HQ in one sentence (daily = Fast; HQ is slow and costs us GPU).
- Batch files in one Generate. Daily pack is **Fast 8** until a Fast 20 of
  their talking-head actually returns files (2026-08-25 timed 20 timed out).
- Do not post all copies the same day (strategy — even DIY).

Mobile: five-tab bar stays Studio · Gallery · Drops · Flows · Drive. Creator
plan hides Flows if we gate Workflows. Team stays under More, and More is
empty for Creator except Log out.

---

## 4. Uniqueness research agent (always-on, never live)

TikFusion ships because someone is always probing. We do the same **on lab
Fast**, with look still signed by a human.

**The agent:**

- Fixture clips: 720 talking-head, 1080 talking-head, motion (the ones we
  already trust).
- Loop: change **one** knob (crop window, chroma, dust, rebuild, seed) →
  encode 2 copies on **lab** `xar25v77v3j27u` (`VF_LAB=1`) → record bits,
  VMAF, preset, filter params, stills.
- Output: a dated note in `docs/ops/lab-fast.md` + “Jeff should look at
  pack `…`.”
- **Never** PATCH live `j0b1q4iuunzhnq`. **Never** raise the 24-bit gate to
  buy a screenshot %. **Never** Pixel AI scramble.

Ideas already in the soup (do not re-litigate unless a lab pack wins look):

- Caption-safe crop (shipped).
- 720 chroma cloud + luma dust (shipped, look-capped).
- Peer uniqueness vs last N **drops**, not only vs the current pack.
- Per-workspace seed so two clients with the same source diverge.
- Shot-aware: do not dust a 1080 talking-head like a 720.

This agent is **ops**, not a Studio tab. First slice: a scheduled Cursor
cloud agent or a `scripts/lab_uniqueness_probe.py` Jeff can run, not an
autonomous live worker.

---

## 5. Do-it-for-you (second product, same engine)

DIY is the tool. DIFM is **strategy + posting labor** on our side.

Internal: a VaryForge VA is a **Team member** on the client workspace (or
we Open-as from Admin). They Generate, Send to Drive / phone, post on a
drip, label Drops, generate-more on winners. They do **not** dump 20 copies
in one afternoon. They do **not** recycle a flagged recipe.

Price DIFM as a **retainer** (hours + quota), not as “unlimited variants.”
COGS is still ~$1/200 Fast files; the bill is the VA + strategy.

Not in v1 DIFM: logging into the client’s Instagram from our servers
(`CLAUDE.md` — no account proxies). VA posts from the client’s device /
Repurpose / their phone, same as today.

---

## 6. Knock-out order (deep setup, shallow first slice)

Do these **in order**. Do not start Stripe, the uniqueness daemon, and DIFM
sales in the same week.

| # | Slice | Done when | Notes |
|---|---|---|---|
| **0** | This brief | You and your homie agree on Creator = 10×20 and DIY vs DIFM | This file |
| **1** | Time one Fast 20 | Numbers in §1 filled | **Done 2026-08-25.** Live Fast 20 of 22s 720 talking-head **timed out at 3600s** (8 done on-worker, 0 returned). Testers stay on Fast 8. |
| **2** | Workspace plan + variant cap | Generate refuses at cap with a human sentence | `tenants.json` + Studio copy. No Stripe. **Shipped this slice.** |
| **3** | Creator nav | Testers see Studio / Gallery / Drops / Drive. Team / Workflows / Admin / Diagnostics hidden | Same catalog, `plan` flag. **Shipped this slice.** |
| **4** | Test-reel invites | 3–5 people on live, Fast 8, they label Drops | Invite-only. Fast 20 of this SKU is blocked by the 3600s cap until uniqueness is cheaper or Jeff raises timeout. |
| **5** | Lab uniqueness loop | One scheduled probe, Jeff still signs look | Lab Fast only |
| **6** | Occupancy (Wave 1) | Second studio does not wait on the first | When two testers overlap |
| **7** | Stripe | Creator / Pro / Agency match the table | After money repeats |
| **8** | DIFM offer | One retainer client, internal VA, drip strategy | After DIY testers exist |

Simple and instant for testers = **1–4**. The rest is how we stay alive as
TikFusion keeps shipping.

---

## 7. Decisions (so we do not re-argue)

| Decision | Call |
|---|---|
| First paid shape | Invite-only Creator: 10 sources × 20 Fast / 30 days |
| Price | **$99** still works as DIY vs Fast-8 COGS (~$2–6/mo); do not sell Fast 20 of this talking-head until a pack returns files |
| HQ in Creator | Off or tiny. Daily packs are Fast |
| Team / Workflows | Pro+ . Not on the first test-reel login |
| Admin / Diagnostics | Jeff only |
| Uniqueness agent | Lab only, human look sign-off |
| DIFM | Retainer + drip. Same Studio. No IG login farm |
| Unlimited | Never, until we have max workers *and* a cap that matches invoice |

## Open (need a yes)

- Exact Fast $/hr from the RunPod invoice line for `varyforge-fast-cpu`
  (using **$0.40/hr** from the public CPU formula until then).
- Whether Jeff raises live Fast **execution timeout** so a 20-pack of this
  uniqueness path can finish (~75–90 min estimated) — **not** done from this
  doc; testers stay on Fast 8.
- Cold-start time-to-first-variant (this run was warm, 842 ms pickup).
- Workflows stays hidden on Creator (already shipped that way).
