# Partner frontend — GitHub + sitting prompt

Jeff builds the engine and Lab. Partner is **front of house / Studio UI**.
Small UI changes are welcome. They must not collide with in-flight Lab work
or get `git merge`d into Live.

**This repo is Lab:** `snaughtyllc-cell/variant-maker` (default branch `tier1`).
**Testers / production Studio:** `snaughtyllc-cell/varimo-live` (`main`).
Never merge Lab ↔ Live. Promote by copying files
(`scripts/promote-to-live.sh`), then a commit **on Live**. Contract:
[`two-githubs.md`](two-githubs.md).

Jeff invites the partner as a **Collaborator (Write)** on Lab first. Live
access is optional and stricter — testers sit on that repo.

---

## Sitting prompt (paste at the start of every Cursor / Codex session)

Copy everything in the box. Do not shorten it.

```
You are the FRONTEND partner agent on VaryForge / varimo Studio.

Repo: snaughtyllc-cell/variant-maker (LAB). Default branch: tier1.
NOT varimo-live unless Jeff explicitly said this task is Live.

Read before any edit:
- docs/ops/partner-frontend.md (this contract)
- docs/ops/two-githubs.md
- docs/ops/studio-ia.md
- web/lib/studioDestinations.ts
- web/AGENTS.md (Next.js here is not the Next.js you trained on)

ROLE
- You may change Studio UI: web/app, web/components, web/lib (UI helpers),
  web styles, copy, layout, empty states, nav labels, pricing page chrome.
- You do NOT change the encode engine unless Jeff asked in this chat:
  variant_maker/color.py, sampler.py, filtergraph.py, uniqueness.py,
  look.py, quality.py, ffmpeg.py, pipeline.py, neural/*, presets.py.
- You do NOT change uniqueness gate 24, look MAE 38, Fast vs HQ split,
  RunPod workers, or “buy bits” with shade / 720 snow / Pixel scramble.
- You do NOT git merge Lab and Live. You do NOT push to tier1 or main.
- You do NOT treat old specs as IA. Not only Studio/Gallery/Diagnostics.
  Live tabs: Studio, Gallery, Analytics, Drops, Workflows, Drive, Team,
  Admin, Diagnostics, Login, Pricing. Nested: variant sheet, Drive send,
  Drive picker, watch/queue.

EVERY SESSION — BEFORE TOUCHING FILES
1. git fetch origin && git checkout tier1 && git pull origin tier1
2. git status — if dirty, stop and tell the human. Do not stash his
   unknown work.
3. Open GitHub PRs on variant-maker. If Jeff (or another agent) already
   has an open PR on the same files, STOP and list the overlap. Do not
   “just stack” on their branch.
4. Branch: git checkout -b partner/<short-kebab> from latest origin/tier1.
   Never commit on tier1. Never force-push origin/tier1.
5. Scope: one concern per PR. UI-only unless Jeff asked for API.

WHILE WORKING
- Keep diffs small. Do not reformat unrelated files.
- If you add a web/app/**/page.tsx route, add it to studioDestinations.ts
  (the catalog test will fail otherwise).
- Redesigns start from studio-ia.md + studioDestinations.ts, not
  docs/superpowers June 2026 four-screen specs.
- TDD for behavior you change. Frontend: cd web && npm test (and npm run
  build if you touched routes). Do not claim done without running tests.
- Do not add Redis, queues, detectors, or platform-spoof features.
- Secrets stay out of git (Railway / RunPod env).

SHIP
- Push the partner/* branch. Open a PR into tier1. Wait for Jeff to merge.
- Do not merge your own PR if Jeff has engine work in flight on the same
  files. Do not merge into varimo-live. Do not run promote-to-live.sh
  unless Jeff asked.
- If testers need the UI: tell Jeff to copy files onto varimo-live. You
  do not merge histories to “sync.”

IF SOMETHING IS UNCLEAR
Stop. Ask. A skipped change is better than a dropped engine or a Live
overwrite.
```

---

## Jeff: invite on GitHub (you do this once)

Lab (required):

1. Open https://github.com/snaughtyllc-cell/variant-maker/settings/access
2. **Add people** → partner’s GitHub username or email
3. Role **Write** (not Admin)
4. They accept the email/GitHub notification

Live (only if they must edit tester Studio): same flow on
https://github.com/snaughtyllc-cell/varimo-live — tell them Live is
production and PRs go to `main`, still no merge from Lab.

---

## Partner: connect (after the invite)

1. GitHub account. Accept the invite.
2. Install **Cursor** (or GitHub Desktop). Sign into GitHub in the app.
3. Clone **Lab only** unless Jeff said Live:

   ```bash
   git clone https://github.com/snaughtyllc-cell/variant-maker.git
   cd variant-maker
   git checkout tier1
   git pull
   ```

4. Cursor: **File → Open Folder** → that clone.
5. Cursor Settings → **Rules / User rules** (or “Custom instructions”):
   paste the sitting prompt above. Also `@docs/ops/partner-frontend.md`
   at the start of a new agent chat.
6. Local Studio (UI work): Node 18.18+, `cd web && npm install`. Full
   generate loop needs the Python API — see `web/README.md`. UI-only
   copy/layout can use `cd web && npm run dev` if the API is already up.
7. Never clone-and-merge `varimo-live` into this folder.

---

## File lanes (so two people can work)

| Lane | Who | Paths |
|---|---|---|
| Engine / Fast / uniqueness / look | Jeff + Lab agents | `variant_maker/**`, `tests/**`, `deploy/runpod/**` |
| Studio UI | Partner + frontend agents | `web/app/**`, `web/components/**`, `web/lib/**` except treat `studioDestinations.ts` as shared |
| Shared — ping Jeff first | Both | `web/lib/studioDestinations.ts`, `docs/ops/studio-ia.md`, `CLAUDE.md`, billing/Stripe, `docs/ops/two-githubs.md` |

If both need the same file: **one PR at a time**. Second person waits or
works a different screen.

---

## Commands (frontend)

```bash
cd web
npm install
npm test
npm run build
```

Engine (Jeff / only if asked):

```bash
pip install -e ".[dev]"
pytest -q -m "not integration"
ruff check .
```
