# Bought Studio redesign — source of truth

**Status:** The hosted Claude Design project is gone. The six-screen desktop
mock still lives in this repo. Live Studio is still the older stacked-card
UI. Do not merge the implementation PR onto testers until Jeff + partner
sign it.

Live testers: https://varyforge-studio-production.up.railway.app  
Promotion is copy files onto `snaughtyllc-cell/varimo-live`, never `git merge`.

## What was bought

Claude Design project **“Page redesign exploration”** (desktop, light-aqua,
six screens). Imported 2026-08-27 as:

- `docs/design/Varimo Web Redesign.dc.html`
- `docs/design/support.js`

Open the HTML locally (needs `support.js` beside it). It is UI-only. It is
not the Live app.

Six screens: **Studio · Gallery · Variant detail · Drops · Flows · Drive**.
Dark left rail, slim context bar, two-column pages (setup beside live
state). Sora + Space Grotesk, teal echo wordmark. Originality pass on the
mock is **~38% vs source** — 65% is typical medium, not a gate.

## What is on Live today

Production still serves the older Studio: top bar, stacked cards, no left
rail. That is expected. Lab redesign never shipped to testers.

## What Jeff already changed on the implementation

The mock is the purchase. The running Lab UI on
`cursor/lab-restore-hq-opt-in-cdb6` (PR #60) also has later product
tweaks. Those are **not** in the `.dc.html` file:

- Reconstruct first (HQ) is a switch, default **off** (not a 20 HQ pack)
- Live/progress rail sized so tiles cannot eat the page (phone **300px**,
  desktop **460px**)
- Gallery clip opens in the review pane (rail + pack list stay)
- Phone chrome: centered wordmark, floating Generate, tighter Gallery
- Originality copy/color from the **38%** pass, not a 65% “verified” band

PR #60 is **CONFLICTING** vs current `tier1` and was marked a dirty dump.
Do **not** merge it onto Live to “get the design back.”

## If the partner signs it

Copy chosen `web/` files onto `varimo-live` / `main` (see
`docs/ops/two-githubs.md`). Do not merge Lab `tier1` into Live. Do not pin
or PATCH live Fast as part of a UI ship.

## Do not

- Treat the expired Claude Design URL as recoverable
- Merge PR #60 without a dedicated conflict pass
- Dump this mock onto Railway production to preview
- Raise the 24-bit uniqueness gate because the mock shows 38%
