# Studio workspaces (invite-only Google login)

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
| **User** | Google email with a session cookie |
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

## Google login

Reuse Drive OAuth client id/secret. Scopes: `openid email profile` only.  
Redirect: `{origin}/api/auth/google/callback`  
(`VARIANT_AUTH_OAUTH_REDIRECT_URI` override). Drive Connect stays a
**second** Google consent with Drive scopes, token file **per workspace**.

Uninvited emails → 403 after Google (“ask Jeff for an invite”).

## HTTP

Public with auth on: `GET /api/health`, `/api/auth/google/start`,
`/api/auth/google/callback`, `/api/auth/me` (returns `{auth_required, …}`).

Everything else (including `/api/variants/...`, `/api/sources/.../source`,
queue, gallery, Drive, captions) **401** without a valid session.

```
GET  /api/auth/me
POST /api/auth/logout
GET  /api/auth/google/start
GET  /api/auth/google/callback
GET  /api/auth/invites          (admin)
POST /api/auth/invites          { email, kind: "join" | "new_workspace" }
DELETE /api/auth/invites/{id}   (admin)
GET  /api/admin/workspaces      (admin) — all studios, counts, no video
POST /api/admin/view            (admin) { workspace_id: string | null }
```

`/api/auth/me` when auth off:

```json
{ "auth_required": false, "email": null, "workspace_id": null,
  "workspace_name": null, "role": null, "is_admin": false }
```

When auth on + session:

```json
{ "auth_required": true, "email": "a@b.com", "name": "A",
  "workspace_id": "ws_…", "workspace_name": "…",
  "home_workspace_id": "ws_…",
  "viewing_other": false,
  "role": "owner" | "member", "is_admin": true }
```

Queue/gallery/jobs/Drive/captions/workflows are **this workspace only**.

## Admin oversight (same Studio)

Not a second app. Admin (`VARIANT_AUTH_ADMIN_EMAIL`) sees an extra **Admin**
control in the existing top nav:

1. **All studios** — list every workspace: name, owner email, live Fast/HQ
   counts, last job time, last error. No video bytes.
2. **Open** — switch the admin session into that workspace. Gallery, queue,
   Generate, Drive, captions look like *theirs*. A banner:
   `Viewing {name} — Exit to your studio`.
3. **Exit** — back to the admin’s own workspace.

Switch is a second cookie (`vf_admin_view`). Home workspace stays on
`vf_session`. Non-admins cannot set the view cookie.

This is how Jeff debugs “their Generate is stuck” without a shared public
gallery.

## Not this

- Postgres, Stripe, public signup, uniqueness changes, per-VA Drive inside
  Jeff’s workspace, R2 key prefix (source ids are unique enough for now)
