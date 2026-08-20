# Studio workspaces (invite-only login)

**Date:** 2026-08-20  
**Status:** Shipped (auth off until `VARIANT_AUTH_ADMIN_EMAIL` is set)  
**Product name:** VaryForge

## Why

One public Studio URL. Jeff + VAs share packs on purpose. Outside operators must
not see those models, captions, or Drive folders. Uniqueness/speed stays frozen.

## Tenant model

| Term | Meaning |
|------|---------|
| **Workspace** | One operator world: gallery, jobs, captions, destinations, Drive token |
| **User** | Invited email with a session cookie (password and/or Google) |
| **Join invite** | Email lands in an *existing* workspace (VAs on Jeff’s) |
| **New-workspace invite** | Email gets an empty workspace + their own Drive connect |
| **Admin** | `VARIANT_AUTH_ADMIN_EMAIL` — can invite; first login claims legacy data |

Auth **off** when `VARIANT_AUTH_ADMIN_EMAIL` is unset (all existing tests).  
Auth **on** when that env is set (production).

## Storage (no Postgres this slice)

JSON at `{DATA_DIR}/auth/tenants.json`. Videos stay files:

`{DATA_DIR}/tenants/{workspace_id}/` — same layout as today’s Workspace
(`jobs/`, `drive/`, `uploads/`, …).

On first admin login, if `jobs/` or `drive/` still sit at DATA_DIR root, move
them into that admin workspace (one-time).

## Session

HttpOnly cookie `vf_session` (HMAC, `VARIANT_AUTH_SECRET` or a file at
`{DATA_DIR}/auth/secret`). Payload: email, workspace_id, exp (7 days).

## Login

Invite-only. No public signup.

**Email + password:** `POST /api/auth/password` `{ email, password }`. First
sign-in for an invited (or admin) email **sets** that password. Later visits
verify it. Google-only accounts (no hash yet) cannot have a stranger set a
password from the login page — they sign in with Google, then add a password
under Drive → Studio password (`POST /api/auth/password/set`).

**Google:** Reuse Drive OAuth client id/secret. Scopes: `openid email profile`
only.
Redirect: `{origin}/api/auth/google/callback`
(`VARIANT_AUTH_OAUTH_REDIRECT_URI` override). Drive Connect stays a
**second** Google consent with Drive scopes, token file **per workspace**.

Uninvited emails → 401 / `not_invited` (“ask the operator for an invite”).

## HTTP

Public with auth on: `GET /api/health`, `/api/auth/password`,
`/api/auth/google/start`, `/api/auth/google/callback`, `/api/auth/me`
(returns `{auth_required, …}`).

Everything else (including `/api/variants/...`, `/api/sources/.../source`,
queue, gallery, Drive, captions) **401** without a valid session.

```
GET  /api/auth/me
POST /api/auth/logout
POST /api/auth/password          { email, password }  (invite/admin; first visit sets hash)
POST /api/auth/password/set      { password }         (logged in)
GET  /api/auth/google/start
GET  /api/auth/google/callback
GET  /api/auth/invites          (admin)
POST /api/auth/invites          { email, kind: "join" | "new_workspace" }
DELETE /api/auth/invites/{id}   (admin)
GET  /api/admin/workspaces      (admin) — studios, members, counts, no video
DELETE /api/admin/users/{email} (admin) — revoke login; cannot remove admin
POST /api/admin/view            (admin) { workspace_id: string | null }
GET  /api/workspace/team        (owner or site admin) — home studio members + pending joins
POST /api/workspace/invites     (owner or site admin) { email } — join into **home** workspace
DELETE /api/workspace/invites/{id} (owner or site admin) — that home invite only
DELETE /api/workspace/members/{email} (owner or site admin) — cannot remove self or site admin
```

`/api/auth/me` when auth off:

```json
{ "auth_required": false, "email": null, "workspace_id": null,
  "workspace_name": null, "role": null, "is_admin": false,
  "has_password": false }
```

When auth on + session:

```json
{ "auth_required": true, "email": "a@b.com", "name": "A",
  "workspace_id": "ws_…", "workspace_name": "…",
  "home_workspace_id": "ws_…",
  "viewing_other": false,
  "role": "owner" | "member", "is_admin": true,
  "has_password": true }
```

Queue/gallery/jobs/Drive/captions/workflows are **this workspace only**.

## Admin oversight (same Studio)

Not a second app. Admin (`VARIANT_AUTH_ADMIN_EMAIL`) sees an extra **Admin**
control in the existing top nav:

1. **All studios** — list every workspace: name, owner email, **who can sign
   in** (email + role), live Fast/HQ counts, last job time, last error. No
   video bytes. **Remove** on a member drops their user (and any pending
   invite). Their next request is 401 until you invite that email again.
   Workspace files stay so you can still Open the studio. You cannot remove
   the admin account.
2. **Open** — switch the admin session into that workspace. Gallery, queue,
   Generate, Drive, captions look like *theirs*. A banner:
   `Viewing {name} — Exit to your studio`.
3. **Exit** — back to the admin’s own workspace.

**Team** (`/team`) is for workspace **owners** (new-workspace operators and
Jeff). Join-invite into the session’s **home** workspace — never the admin
view cookie. Members cannot invite. `new_workspace` stays site Admin only.
If the owner is bringing their own VA, they use Team, not Jeff.

Switch is a second cookie (`vf_admin_view`). Home workspace stays on
`vf_session`. Non-admins cannot set the view cookie.

This is how Jeff debugs “their Generate is stuck” without a shared public
gallery.

## Later (speed — not this slice)

Workspaces split **data** (gallery, Drive, captions), not hardware. Every studio
still shares the same Fast CPU endpoint and the one HQ GPU. Adding a partner
does not give them their own cards.

Jeff’s notes (2026-08-20), parked — do not start this while invites/login land:

- **Pain is interactive 1–2 clips**, not the Drive workflow. Workflow pull →
  generate → send can stay slow; nobody is waiting on the button. Studio
  Generate for one or two files is the gap.
- **Telegram spoofer** (unnamed bot): one clip comes back in **seconds to ~1
  minute**; bigger jobs **~1–2 minutes**. Jeff’s guess: an always-on runner
  (warm), plus we do not know which transforms / uniqueness / quality loop it
  uses. Optional later: he can send a spoofed output so we can probe what it
  actually did (resolution, filters, whether it skipped a quality/uniqueness
  ladder). Not a detector; not cloning that bot.
- **TikFusion** is the closer product; maybe a tad quicker than us last he
  used it.
- Earlier the same day: 5 minutes for **one** Fast variant feels too slow;
  5 minutes for an 8-pack is fine.

When we come back: extra Fast workers / more parallelism so one person’s job
doesn’t sit on a cold or serial worker; measure warm vs cold start. Do
**not** raise uniqueness floors or turn escalate off as a speed hack. Do not
split Fast across CPU+GPU. Do not always-on GPU. Always-on Fast CPU is a
cost trade to discuss then, not a default.

### Hybrid runners (two Fast CPUs)

Jeff (2026-08-20): if workspace A is on a Fast CPU job, boot a **second**
serverless CPU for workspace B instead of one shared queue. If only one
studio is generating, they keep the single worker (no extra spend). Same
pattern later for a second HQ GPU.

Occupancy lives in `FastOccupancy` / `RoutingRunner`. Env:
`RUNPOD_FAST_ENDPOINT_ID` (primary) + `RUNPOD_FAST_ENDPOINT_ID_2` (overflow).
Still scale-to-zero. Still Fast = CPU, HQ = GPU. Do not split one pack
across CPU+GPU. Do not always-on GPU.

## Not this

- Postgres, Stripe, public signup, uniqueness changes, per-VA Drive inside
  Jeff’s workspace, R2 key prefix (source ids are unique enough for now)
