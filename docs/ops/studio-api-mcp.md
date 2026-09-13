# Studio API + MCP

Status: **Phase 2 on Lab**. HTTP workspace keys + `/api/v1` + stdio
`varimo-mcp`. Hosted remote MCP is not built. Date: 2026-09-13.

Do not `git merge` Lab ↔ Live. After a separate Lab accept, copy files with
`scripts/promote-to-live.sh`. No Live Fast pin or `:latest` push from this work.

How-to stays a human loop. This screen is **Settings → Integrations**.

## What shipped (Phase 1)

The workspace **owner** (home studio only — not a VA, not an admin viewing
another workspace) issues a key. That key is **not** a Studio login. It can
only call `/api/v1`. Cookie UI keeps today’s `/api/*` routes.

| Route | Scope | What it does |
|---|---|---|
| `POST /api/v1/packs` | `jobs:create` | One Fast pack from one Drive clip already in a configured folder. `count` is 8 or 20. Requires `Idempotency-Key`. |
| `GET /api/v1/packs/{pack_id}` | `jobs:read` | State, ready counts, shortfall, copy indexes. Review URL is Gallery. |
| `GET /api/v1/gallery` | `gallery:read` | Safe metadata page (`limit`, `cursor`, optional `pack_id`). |
| `POST /api/v1/drive/exports` | `drive:export` | Selected ready copies to an existing destination. No caption-bank consume. No split. Requires `Idempotency-Key`. |
| `GET /api/v1/drive/exports/{export_id}` | `drive:export` | Export state until it finishes. |

Contract JSON: `GET /api/v1/openapi.json` (no key).

Keys: `GET/POST /api/workspace/api-keys`, `DELETE /api/workspace/api-keys/{key_id}`.
Cookie only. Token format `vf_<key_id>_<secret>`. Digest stored; plaintext once.
Default expiry 90 days (owner can pick 30). Presets: **full** (all four scopes)
or **read** (`jobs:read` + `gallery:read`).

Auth off (`VARIANT_AUTH_ADMIN_EMAIL` unset): key issue and bearer are off.

## Operator loop

1. Connect Drive and add input / output folders.
2. Create a key on Integrations. Copy it once.
3. From the agency machine:

```bash
export VARIMO_BASE_URL="https://your-studio.example"
export VARIMO_API_KEY="vf_…"   # never paste this into chat or a screenshot

curl -sS -X POST "$VARIMO_BASE_URL/api/v1/packs" \
  -H "Authorization: Bearer $VARIMO_API_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"input_destination_id":"dst_…","drive_file_id":"…","count":8}'

curl -sS "$VARIMO_BASE_URL/api/v1/packs/PACK_ID" \
  -H "Authorization: Bearer $VARIMO_API_KEY"
```

4. Open Gallery in Studio to check the look.
5. Export selected copies (`source_id` + `index`) to the output folder.
6. Point Repurpose.io / Buffer at that folder. We do not run those seats.

A key spends the same Fast processing as Generate. There is no separate MCP
fee and no extra weekly cap to document here.

## Phase 2 — `varimo-mcp`

Install extra `.[mcp]`. Executable `varimo-mcp`. Stdio only. Reads
`VARIMO_BASE_URL` and `VARIMO_API_KEY`. Calls only `/api/v1`. Tools:
`create_pack`, `get_pack`, `list_gallery`, `send_to_drive` (submit **or**
`export_id` status — not both). HTTPS except localhost HTTP for Lab. Redirects
are refused so the key is not forwarded. Logs go to stderr.

## Not in v1

Workflow triggers, caption-bank, HQ, uploads/URLs, raw media download,
Instagram, webhooks, split export, per-folder ACLs, hosted remote MCP.
Hard client split = another workspace.

Do not document fingerprint or uniqueness internals (SHA / AAC / SEI / encode
tags / gate 24 / MAE 38 / SSIM / VMAF as a recipe) in customer API copy.

## Lab notes

- Storage: `{data_dir}/auth/api_keys.json` next to `tenants.json`. JSON, not
  SQLite. Corrupt file fails closed.
- Bearer on any non-`/api/v1` path is 401 even with a valid cookie.
- Cookie cannot call `/api/v1`.
- Site admin env is `VARIANT_AUTH_ADMIN_EMAIL` (one email).
