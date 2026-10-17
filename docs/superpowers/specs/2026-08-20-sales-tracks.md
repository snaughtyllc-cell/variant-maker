# Sales-ready parallel tracks

**Date:** 2026-08-20  
**Status:** Active — spawn one track per agent; do not share files across tracks  
**Product name:** VaryForge

Invite-only Studio is live. Next work is to sell / onboard operators without
turning uniqueness, escalate, or GPU always-on into speed hacks.

## How to parallelize

One agent per track. Stay inside that track’s **file box**. If you need a file
from another box, stop and hand off — do not “just fix it.”

Site-admin (`VARIANT_AUTH_ADMIN_EMAIL`) stays Jeff. Workspace **owners** run
their own team. Hardware is still shared until Track D.

## Track A — Agency / team (this slice)

**Status:** Shipped on Studio PR — `/team` for owners + site admin.

**Why:** A new-workspace operator must add their own VAs. Site Admin still
creates empty studios.

**Ship:** `/team` for `role=owner` (and site admin). Join-invite into **home**
workspace only. Remove member (not self, not site admin). Pending invites
listed. No `new_workspace` from Team — that stays site Admin.

**Box:** `variant_maker/server/tenants.py`, `app.py` workspace routes,
`web/app/team/`, `web/components/nav/TopNav.tsx`, `web/lib/api.ts` team
helpers, `tests/server/test_auth_app.py`, `web/tests/TeamPage.test.tsx`

**Not:** RunPod, uniqueness, Drop Ledger, billing.

## Track B — Tracking / Drop Ledger UX

**Why:** Agencies need “what we posted / what got flagged” without living in
Sheets. Spec already exists; PLAN Phase 12 was skipped until asked.

**Ship (12a only):** Studio Ensure/Sync for the Drop Ledger sheet. Gallery
already has Passed / Duplicate rejected. Unlabeled = pass. Do not build a
detector. Do not key on caption filenames (Repurpose renames).

**Box:** `docs/superpowers/specs/2026-08-18-platform-outcome-learning.md`,
`variant_maker/server/drop_ledger.py`, drop-ledger routes in `app.py` (only
those), `web/app/gallery/` / variant sheet if labeling copy, `web/components/drive/`
ledger panel only.

**Not:** auth/tenants, sampler, RunPod workers, Team page.

## Track C — Operator onboarding copy

**Why:** First paid operator should Connect Drive, invite VAs, Generate Fast
20, Send to Drive, without Jeff on a call.

**Ship:** A short operator page in `docs/ops/` (Drive connect, Team, Fast vs
HQ, workflow vs one-off). Link from Team + Drive empty states. No new auth.

**Box:** `docs/ops/`, empty-state strings on Drive / Team pages only.

**Not:** engine, uniqueness, workers.

## Track D — Smart / hybrid runners (parked)

**Why:** Three busy workspaces on one Fast CPU endpoint = one queue. Jeff’s
idea: if workspace A is using a Fast worker, boot a **second** serverless
CPU for workspace B; if only one workspace is busy, they keep the one
worker. Same idea later for HQ GPUs.

**Do not build this track yet.** Notes live on the workspaces spec
(`Later — hybrid runners`). Constraints when we do:

- Extra Fast **CPU** endpoints (scale to zero), not always-on GPU.
- Do not split **one pack** across CPU+GPU.
- Do not raise uniqueness floors or turn escalate off.
- Route by “this workspace has a live Fast job,” not by selling a dedicated
  card per customer on day one.

**Box (when unparked):** `variant_maker/server/runpod_runner.py`,
`runner.py`, `docs/ops/railway-studio.md`, RunPod env. Not auth UI.

## Do not start in parallel (single-threaded)

- Interactive 1–2 clip **speed** vs Telegram (parked; needs timing).
- Stripe / public signup / Postgres.
- Always-on GPU.
- Uniqueness 55% / raising 24-bit gates.
- Cloning TikFusion Pixel AI or Telegram bots.

After A/B/C are in operators’ hands, next-wave order (hybrid runners →
1–2 clip speed → HQ occupancy → Drop Ledger 12b/12c → billing last) is
`docs/superpowers/specs/2026-08-20-after-sales-tracks.md`.

