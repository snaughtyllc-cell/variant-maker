# Studio information architecture (redesign source of truth)

Codex and any other redesign pass must use this page, not the four-row
"Screens" table that used to live in `web/README.md`. That table was the
first-version list (Studio / Gallery / Variant side-panel / Diagnostics)
and hid every destination shipped after v1.

Live product: https://varyforge-studio-production.up.railway.app

Purchased desktop redesign (Claude Design project expired; mock is in-repo):
`docs/ops/bought-design.md` and `docs/design/Varimo Web Redesign.dc.html`.
Live still uses the older stacked-card UI until that mock is signed and
copied onto `varimo-live`.

Machine-readable catalog: `web/lib/studioDestinations.ts`.
`TopNav` renders `PRIMARY_TABS` / `EXTRA_TABS` from that file.
The catalog test (`web/lib/__tests__/studioDestinations.test.ts`)
fails if a `web/app/**/page.tsx` route is missing from the list.

Historical June 2026 frontend specs (`docs/superpowers/specs/2026-06-29-control-plane-frontend-design.md`
and `docs/superpowers/plans/2026-06-29-control-plane-frontend.md`)
describe v1 only. Do not treat them as the current product.

## Who sees what

| Audience | Tabs |
|---|---|
| Everyone signed in | **Studio · Gallery · Analytics · Drops · Workflows · Drive · How to** |
| Workspace owner (or site admin) | + **Team** |
| Home-workspace owner | + **Integrations** (hidden while viewing another studio) |
| Site admin (`VARIANT_AUTH_ADMIN_EMAIL`) | + **Admin · Diagnostics** |
| Unauthenticated | **Login** and **Pricing** |

Solo owners see **Studio · Gallery · Analytics** on the phone bar; Drive
and How to sit under More. Solo members see **Studio · Gallery**, with Drive
and How to in More.

Phone (`< 640px`) shows **Studio · Gallery · Analytics · Flows**.
**Drive**, **Drops**, and **How to** sit under the top-right **More** control,
with Team / Admin / Diagnostics. Desktop SideNav keeps the full operator row
(Studio / Gallery / Drops / Workflows / Drive) and How to in extras.

Watch is **not** a tab. It lives inside Studio + Workflows as a job
row + progress card.

## Destinations (complete)

| Tab | Route | Audience | Phone bar | What it is |
|---|---|---|---|---|
| Studio | `/` | everyone | yes | Drop files or pick from Drive, set copies, Fast, Reconstruct-first (HQ) switch default off, Advanced, live queue. |
| Gallery | `/gallery` | everyone | yes | 7-day packs by source. Thumbs, uniqueness, Send to Drive, Sent/Flagged chips. |
| Analytics | `/analytics` | owner / site admin | yes | Instagram Insights scoreboard: connected testers, pack totals, ranked originals, Sync, generate more of a winner. |
| Workflows | `/workflows` | everyone | yes (label **Flows**) | Watch folder auto-poll, inbox-to-output Drive folders, cancel a live pack. |
| Drops | `/drops` | everyone | More | Drive-sent packs this week. Unlabeled = pass. Flagged / duplicate rejected = miss. |
| Drive | `/settings/drive` | everyone | More | Share varimo Drive email, paste folder link, captions, Drop Ledger, Instagram testers, password. |
| How to | `/how-to` | everyone | More | Three tabs: Generating (Studio→Gallery), Automation (Workflows, auto captions, Repurpose/Buffer plugins), Posting. No Analytics. No fingerprint internals. |
| Team | `/team` | owner / site admin | More | Workspace owner invites VAs into this studio. |
| Integrations | `/settings/integrations` | owner (home workspace) | More | Owner-issued workspace API keys. Fast packs, Gallery metadata, Drive export. Not inside Drive. Not a phone-bar tab. |
| Admin | `/admin` | site admin | More | Workspaces, join/new-workspace invites, view-as. |
| Diagnostics | `/diagnostics` | site admin (or auth off) | More | Failed encodes (`uniqueness_fail` / `corrupt` / `best_effort`). Operators never use this. |
| Login | `/login` | unauthenticated | — | Email + password or Google after checkout or an invite. No app tabs. |
| Pricing | `/pricing` | unauthenticated | — | Agency Stripe Checkout. Webhook invites the payer. Landing can link here. |

## Nested surfaces a redesign must include

These are not tabs. They open from a parent destination and must stay
in the redesign, not get dropped because they are missing from the
old four-row list.

| Surface | Parent | How it opens |
|---|---|---|
| Variant sheet | Gallery | Tap a finished copy. Compare slider, scrub, quality, uniqueness, platform flag, post URL, download. |
| Instagram compact views | Gallery pack header / tile / variant sheet | Views rollup line, linked count, quiet/winner hint. Full scoreboard lives on Analytics. |
| Send to Drive | Gallery / variant sheet | Pick destination + caption folder; split a pack across folders. |
| Drive picker | Studio | Import source files from a saved Drive destination. |
| Watch / queue / cancel | Studio + Workflows | Live job tiles, cancel, re-attach after reload. |

## Later (do not build yet)

| Idea | Why it waits |
|---|---|
| **Announcements** — in-app updates / bug-fix notes so operators see what shipped (Jeff 2026-08-29) | Not a seventh phone tab. Not a Fast/uniqueness change. Park until a wave above is idle. When built: everyone signed in, short dated notes, no marketing blog. |
| **Cut Analytics / testers** (Jeff 2026-09-13) | Not sure Studio ever shifts to Insights. How-to does **not** teach testers. Do not remove the Analytics tab in a drive-by. Park the cut until Jeff signs it. |

Instagram Analytics is still a live tab today (not gone). Scoreboard on
Analytics; compact views on Gallery. Ops: `docs/ops/instagram-testers.md`.
Spec: `docs/superpowers/specs/2026-09-02-instagram-insights-gallery.md`.
How-to does not mention it.

## What not to invent

- Do not add a Watch tab. Watch stays inside Studio + Workflows.
- Do not add an Updates / Announcements tab in a redesign pass. It is
  parked under Later above — not missing IA.
- Do not hide Analytics, Drops, Workflows, Drive, Team, Admin, How to, or
  Integrations — they are live.
- Do not put Admin / Diagnostics / Drive / Drops / How to / Integrations in the
  phone bottom bar. Drive, Drops, How to, and Integrations stay under More.
  Admin / Diagnostics stay under More.
- How-to copy is posting hygiene. Do not document fingerprint internals
  (SHA / AAC / SEI / encode tags) on that page.
- Auth gating stays in `web/lib/navAccess.ts` (`showTeamNav`,
  `showIntegrationsNav`, `showDiagnosticsNav`, `extraTabVisible`). Site admin is
  `VARIANT_AUTH_ADMIN_EMAIL` (docs that still say `SITE_ADMIN_EMAILS` are drift).
