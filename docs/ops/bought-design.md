# Bought Studio redesign — source of truth

**Status:** The hosted Claude Design project is gone. The six-screen desktop
mock still lives in this repo. **Smoke the running redesign on Lab Studio
first.** Do not copy it onto Live testers until Jeff + partner sign the Lab
URL.

Lab smoke: https://varyforge-studio-lab.up.railway.app  
Live testers: https://varyforge-studio-production.up.railway.app  
Promotion is copy files onto `snaughtyllc-cell/varimo-live`, never `git merge`.

## Easiest Lab-first path (do this)

Do **not** merge dirty PR **#60** (`cursor/lab-restore-hq-opt-in-cdb6`). That
branch is the old running redesign plus a stale engine and a lab-only HQ
gate. Merging it onto `tier1` would drop later Lab product.

The smoke branch is **`cursor/lab-redesign-smoke-cdb6`**: current Lab
`tier1` engine + the bought `web/` overlay, with Lab product kept:

- Reconstruct first (HQ) switch, **always visible**, default **off**
- Originality honesty (pixel SSIM / 3 frames / not a platform check)
- Save-to-phone progress (no prefetch on Select all)
- Drive **Connect Google** is site admin only

Merge that PR onto **`tier1`**. Lab Railway auto-deploys this repo’s Lab
env from `tier1`. That Lab URL is the smoke test.

After they sign Lab, copy chosen `web/` files onto `varimo-live` / `main`
(see `docs/ops/two-githubs.md`). Do not merge Lab `tier1` into Live. Do not
pin or PATCH live Fast as part of a UI ship.

## What was bought

Claude Design project **“Page redesign exploration”** (desktop, light-aqua,
six screens). Frozen in-repo as:

- `docs/design/Varimo Web Redesign.dc.html`
- `docs/design/support.js`

Open the HTML locally (needs `support.js` beside it). It is UI-only. It is
not the Live app. Mock freeze PR: **#83**.

Six screens: **Studio · Gallery · Variant detail · Drops · Flows · Drive**.
Dark left rail, slim context bar, two-column pages (setup beside live
state). Sora + Space Grotesk, teal echo wordmark. Originality pass on the
mock is **~38% vs source** — 65% is typical medium, not a gate.

## What is on Live today

Production still serves the older Studio: top bar, stacked cards, no left
rail. That is expected. Lab redesign never shipped to testers.

## What Jeff already changed on the implementation

The mock is the purchase. The running Lab UI also has later product tweaks.
Those are **not** in the `.dc.html` file:

- Reconstruct first (HQ) is a switch, default **off** (not a 20 HQ pack)
- Live/progress rail sized so tiles cannot eat the page (phone **300px**,
  desktop **460px**)
- Gallery clip opens in the review pane (rail + pack list stay)
- Phone chrome: centered wordmark, floating Generate, tighter Gallery
- Originality copy/color from the **38%** pass, not a 65% “verified” band

PR #60 is **CONFLICTING** vs current `tier1` and was marked a dirty dump.
Do **not** merge it onto Lab or Live to “get the design back.” Use the
overlay PR instead.

## Do not

- Treat the expired Claude Design URL as recoverable
- Merge PR #60 onto `tier1` or Live
- Dump this mock onto Railway production to preview
- Point Lab Railway at the stale #60 engine
- Raise the 24-bit uniqueness gate because the mock shows 38%
