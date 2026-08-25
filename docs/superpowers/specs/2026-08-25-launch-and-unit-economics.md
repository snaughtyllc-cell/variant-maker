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
| Fast CPU `cpu3g-8-32` | **~$0.25–$0.45 / worker-hour** | RunPod does not publish a stable public CPU serverless table; invoice is source of truth. |
| HQ 4090-class serverless | **~$0.40–$0.70 / worker-hour** | Same: per-second flex. Idle 10 min after HQ is the expensive surprise. |
| Railway Studio + volume | **~$20–60 / month** shared | All workspaces share one URL. Do not allocate this 1:1 to one tester. |
| Object storage | **near $0** at 24h gallery TTL | Packs expire; R2 is a mailbox, not a film archive. |

Until we time a real pack, treat Fast encode as:

| Clip | Copies | Worker time (encode, 1 worker, sequential) | + 10 min idle if this was the last job |
|---|---|---|---|
| ~15–30s talking-head 720 Fast | 20 | **~8–20 min** (plan **15 min**) | +10 min |
| Same × **10 sources in one Generate** | 200 | **~80–200 min** (plan **2.5 h**) | +10 min once |
| Same × 10 sources as **10 separate clicks** hours apart | 200 | same encode | **+10 min × 10** |

### Worked example — 10 sources × 20 Fast copies (the question)

Assume **15 min encode / source**, one Generate with all 10 files, Fast CPU
**$0.35/hr** (mid-band):

| Piece | Time | Cost |
|---|---|---|
| Encode 10 × 15 min | 2.5 h | **$0.88** |
| One cooldown | 0.17 h | **$0.06** |
| **COGS compute** | | **~$0.94** |
| Railway + storage share | | **~$0.05–0.20** this pack |
| **All-in COGS** | | **~$1.00–1.20** for 200 files |

If they fire 10 separate Generates across the day: extra **~9 × 10 min idle ≈
$0.53**. Same 200 files, **~50% more compute**. Product rule: **one Generate
with N sources**, not N clicks.

**Per-variant Fast COGS ≈ $0.005–$0.01** at that band (clip length dominates).

HQ is **not** this math. A 20 HQ pack can sit on a 4090 for a long time; do
not sell HQ as the daily 20. HQ is the upsell / hard talking-head.

### What we still must measure (one test-reel pack)

On the **next** real Fast 20 of a typical talking-head, write down:

- Worker start → last `ok` (RunPod request duration)
- Studio “done” (includes R2 copy-back)
- Clip duration + resolution
- Copies requested vs delivered
- Idle whether another job landed inside 10 min

Paste into this spec. Pricing without that row is a band, not a quote.

### Margin (use after the timed pack)

Sell **the month**, not the second.

| If they pay | For 200 Fast copies/mo | Gross on ~$1.20 COGS |
|---|---|---|
| $49 | test / creator | ~40× |
| $99 | default DIY | ~80× |
| $149 | comfortable DIY | ~120× |

Compute is cheap. **What eats margin:** HQ, two agencies generating at once
(second Fast worker), idle 10 min on sparse clicks, uniqueness escalate
re-encodes, and **VA time** on DIFM.

Do not price DIY at TikFusion “unlimited” until max workers and quotas exist.
Two concurrent 10×20 jobs = two Fast CPUs billed in parallel.

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
3. **Then** 20-copy packs once they trust look.
4. **Quota cap** in `tenants.json` before the third tester, so one person
   cannot sit on both Fast workers for a weekend.
5. Stripe / self-serve only when Jeff is the invite bottleneck **and** money
   is repeating (`after-sales-tracks` Wave 6).

Onboarding copy they need on-screen, not a PDF:

- Fast vs HQ in one sentence (daily = Fast; HQ is slow and costs us GPU).
- Batch files in one Generate.
- Do not post all 20 the same day (strategy — even DIY).

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
| **1** | Time one Fast 20 | Numbers in §1 filled | Next test-reel pack |
| **2** | Workspace plan + variant cap | Generate refuses at cap with a human sentence | `tenants.json` + Studio copy. No Stripe. **Shipped this slice.** |
| **3** | Creator nav | Testers see Studio / Gallery / Drops / Drive. Team / Workflows / Admin / Diagnostics hidden | Same catalog, `plan` flag. **Shipped this slice.** |
| **4** | Test-reel invites | 3–5 people on live, Fast 8 then 20, they label Drops | Invite-only |
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
| Price | Set after timed pack; **$99** is the working DIY placeholder, not a promise |
| HQ in Creator | Off or tiny. Daily packs are Fast |
| Team / Workflows | Pro+ . Not on the first test-reel login |
| Admin / Diagnostics | Jeff only |
| Uniqueness agent | Lab only, human look sign-off |
| DIFM | Retainer + drip. Same Studio. No IG login farm |
| Unlimited | Never, until we have max workers *and* a cap that matches invoice |

## Open (need the timed pack or a yes)

- Exact Fast $/hr from the RunPod invoice line for `varyforge-fast-cpu`.
- Creator at 8 copies vs 20 for the first week of testers (20 is the sell;
  8 is faster to love).
- Whether Workflows stays visible on Creator (hidden is simpler).
