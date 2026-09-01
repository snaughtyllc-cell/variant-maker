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

| Audience | Tabs |
|---|---|
| Everyone signed in | **Studio · Gallery · Drops · Workflows · Drive** |
| Workspace owner (or site admin) | + **Team** |
| Site admin (`SITE_ADMIN_EMAILS`) | + **Admin · Diagnostics** |
| Unauthenticated | **Login** only |

Phone (`< 640px`) only has room for the five everyone-tabs. Team /
Admin / Diagnostics sit under **More**. Desktop shows extras in the
top row when the session is allowed to see them.

Watch is **not** a tab. It lives inside Studio + Workflows as a job
row + progress card.

## Destinations (complete)

| Tab | Route | Audience | Phone bar | What it is |
|---|---|---|---|---|
| Studio | `/` | everyone | yes | Drop files or pick from Drive, set copies, Fast, optional Reconstruct first (HQ), Advanced, live queue. |
| Gallery | `/gallery` | everyone | yes | 7-day packs by source. Thumbs, uniqueness, Send to Drive, Sent/Flagged chips. |
| Drops | `/drops` | everyone | yes | Drive-sent packs this week. Unlabeled = pass. Flagged / duplicate rejected = miss. |
| Workflows | `/workflows` | everyone | yes (label **Flows**) | Watch folder auto-poll, inbox-to-output Drive folders, cancel a live pack. |
| Drive | `/settings/drive` | everyone | yes | Share varimo Drive email, paste folder link, captions, Drop Ledger, password. |
| Team | `/team` | owner / site admin | More | Workspace owner invites VAs into this studio. |
| Admin | `/admin` | site admin | More | Workspaces, join/new-workspace invites, view-as. |
| Diagnostics | `/diagnostics` | site admin (or auth off) | More | Failed encodes (`uniqueness_fail` / `corrupt` / `best_effort`). Operators never use this. |
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

## Later (do not build yet)

| Idea | Why it waits |
|---|---|
| **Announcements** — in-app updates / bug-fix notes so operators see what shipped (Jeff 2026-08-29) | Not a sixth phone tab. Not a Fast/uniqueness change. Park until a wave above is idle. When built: everyone signed in, short dated notes, no marketing blog. |

## What not to invent

- Do not add a Watch tab. Watch stays inside Studio + Workflows.
- Do not add an Updates / Announcements tab in a redesign pass. It is
  parked under Later above — not missing IA.
- Do not hide Drops, Workflows, Drive, Team, or Admin — they are live.
- Do not put Admin / Diagnostics in the phone bottom bar. They stay
  under More.
- Auth gating stays in `web/lib/navAccess.ts` (`showTeamNav`,
  `showDiagnosticsNav`). Site admin is `SITE_ADMIN_EMAILS`.
