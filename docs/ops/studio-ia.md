# Studio information architecture (redesign source of truth)

Codex and any other redesign pass must use this page, not the four-row
"Screens" table that used to live in `web/README.md`. That table was the
first-version list (Studio / Gallery / Variant side-panel / Diagnostics)
and hid every destination shipped after v1.

Live product: https://varyforge-studio-production.up.railway.app

Machine-readable catalog: `web/lib/studioDestinations.ts`.
`TopNav` renders `PRIMARY_TABS` / `EXTRA_TABS` from that file.
The catalog test (`web/lib/__tests__/studioDestinations.test.ts`)
fails if a `web/app/**/page.tsx` route is missing from the list.

Historical June 2026 frontend specs (`docs/superpowers/specs/2026-06-29-control-plane-frontend-design.md`
and `docs/superpowers/plans/2026-06-29-control-plane-frontend.md`)
describe v1 only. Do not treat them as the current product.

## Who sees what

Plan is on the **workspace** (`tenants.json` `plan`, default **internal**).
New-workspace invites land on **Creator**. Catalog still lists every tab;
nav hides extras the plan does not include. See `docs/ops/launch.md`.

| Audience | Tabs |
|---|---|
| Creator plan | **Studio · Gallery · Drops · Drive** (no Workflows, no Team, no HQ) |
| Pro / Agency | + **Workflows**; owners + **Team** |
| Internal (Jeff, missing plan) | all operator tabs |
| Site admin (`SITE_ADMIN_EMAILS`) | + **Admin · Diagnostics** |
| Unauthenticated | **Login** only |

Phone (`< 640px`) shows the primary tabs the plan allows. Team /
Admin / Diagnostics sit under **More**. Desktop shows extras in the
top row when the session is allowed to see them.

Watch is **not** a tab. It lives inside Studio + Workflows as a job
row + progress card.

## Destinations (complete)

| Tab | Route | Audience | Phone bar | What it is |
|---|---|---|---|---|
| Studio | `/` | everyone | yes | Drop files or pick from Drive, set copies, Fast vs HQ, Advanced, live queue. |
| Gallery | `/gallery` | everyone | yes | 24h packs by source. Thumbs, uniqueness, Send to Drive, Sent/Flagged chips. |
| Drops | `/drops` | everyone | yes | Drive-sent packs this week. Unlabeled = pass. Flagged / duplicate rejected = miss. |
| Workflows | `/workflows` | everyone | yes (label **Flows**) | Watch folder auto-poll, inbox-to-output Drive folders, cancel a live pack. |
| Drive | `/settings/drive` | everyone | yes | Connect Google, destinations, caption bank, Drop Ledger, password. |
| Team | `/team` | owner / site admin | More | Workspace owner invites VAs into this studio. |
| Admin | `/admin` | site admin | More | Workspaces, join/new-workspace invites, view-as. |
| Diagnostics | `/diagnostics` | site admin (or auth off) | More | Failed encodes (`below_floor` / `corrupt` / `best_effort`). Operators never use this. |
| Login | `/login` | unauthenticated | — | Invite-only email + password or Google. No app tabs. |

## Nested surfaces a redesign must include

These are not tabs. They open from a parent destination and must stay
in the redesign, not get dropped because they are missing from the
old four-row list.

| Surface | Parent | How it opens |
|---|---|---|
| Variant sheet | Gallery | Tap a finished copy. Compare slider, scrub, quality, uniqueness, platform flag, post URL, download. |
| Send to Drive | Gallery / variant sheet | Pick destination + caption folder; split a pack across folders. |
| Drive picker | Studio | Import source files from a saved Drive destination. |
| Watch / queue / cancel | Studio + Workflows | Live job tiles, cancel, re-attach after reload. |

## What not to invent

- Do not add a Watch tab. Watch stays inside Studio + Workflows.
- Do not drop Drops, Workflows, Drive, Team, or Admin from the **catalog** —
  they are live. Creator **nav** hides Workflows and Team by plan; that is
  intentional (`showWorkflowsNav` / `showTeamNav` + `plan`).
- Do not put Admin / Diagnostics in the phone bottom bar. They stay
  under More.
- Auth gating stays in `web/lib/navAccess.ts` (`showTeamNav`,
  `showWorkflowsNav`, `showDiagnosticsNav`). Site admin is `SITE_ADMIN_EMAILS`.
