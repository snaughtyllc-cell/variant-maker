# Ops runbook: Studio Google Drive OAuth on RunPod

**Audience:** operators redeploying / migrating the varimo Pod  
**Auth path that works:** Web OAuth client (**not** service-account JSON keys)  
**Branch:** `tier1` (OAuth extension for Studio Drive export)

---

## What works

Studio Drive export uses **company Google OAuth** (option C):

1. Pod has OAuth client env vars loaded.
2. Operator opens Studio → **Settings → Drive** → **Connect Google**.
3. Consent as the company Drive account; refresh token is stored on the Pod.
4. Add **destinations** (paste shared folder links the connected account can edit).
5. **Gallery** → select `ok` variants → **Send to Drive**.

Service-account JSON keys are often blocked by org policy. Prefer OAuth; do not rely on SA keys for the working path.

---

## Spec / plan pointers

| Doc | Role |
|-----|------|
| [`docs/superpowers/specs/2026-07-21-drive-export-design.md`](../superpowers/specs/2026-07-21-drive-export-design.md) | Design: Gallery Send to Drive, destinations, SA **or** OAuth |
| [`docs/superpowers/plans/2026-07-21-drive-export.md`](../superpowers/plans/2026-07-21-drive-export.md) | Implementation plan |
| OAuth Connect Google | Landed on **`tier1`** (Studio Settings + callback + token file) |
| [`deploy/pod/README.md`](../../deploy/pod/README.md) | Broader Pod bootstrap notes (ports / bootstrap) |

Farm inbox automation (`2026-06-27-drive-farm-automation-design.md`) is a **different** feature — not this Studio export path.

---

## Current Pod (as of last successful deploy)

> These change on Pod migration / recreate. Treat as a snapshot, not permanent.

| Item | Value |
|------|--------|
| SSH | `ssh root@213.192.2.76 -p 40082 -i ~/.ssh/runpod_variantfarm` |
| SSH key note | Prefer `~/.ssh/runpod_variantfarm`. Fallback `id_ed25519` is often missing locally. |
| UI (proxy) | `https://4favaamr1akoda-8888.proxy.runpod.net` |
| Restart Studio | `bash /workspace/start-varyforge.sh` |
| Restart Comfy (localhost) | `bash /workspace/start-comfy.sh` — **127.0.0.1:8188 only**, not on proxy |
| Restart both | `bash /workspace/start-all.sh` |
| GPU (snapshot) | 1× NVIDIA RTX PRO 6000 Blackwell Server Edition |

Drive Settings URL shape:

`https://<POD_ID>-8888.proxy.runpod.net/settings/drive`

---

## Secrets (never commit real values)

**On Pod:** `/workspace/secrets/drive-oauth.env` (`chmod 600`)

Required variables:

```bash
VARIANT_DRIVE_OAUTH_CLIENT_ID="….apps.googleusercontent.com"
VARIANT_DRIVE_OAUTH_CLIENT_SECRET="…"
VARIANT_DRIVE_OAUTH_REDIRECT_URI="https://<POD_ID>-8888.proxy.runpod.net/api/drive/oauth/callback"
```

**Example (placeholders only):** [`deploy/pod/drive-oauth.env.example`](../../deploy/pod/drive-oauth.env.example)

After Connect Google, token file (do not commit):

`/workspace/vmdata/drive/oauth_token.json`

Optional legacy SA path (often blocked): `VARIANT_DRIVE_SERVICE_ACCOUNT_JSON` — not required when OAuth works.

---

## Google Cloud Console setup

1. [Google Cloud Console](https://console.cloud.google.com/) → select/create project.
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **OAuth consent screen**
   - **Internal** (Google Workspace org) — preferred when available.
   - **External** — if Internal is blocked by org policy; add test users / publish as needed.
4. **Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application** (not Desktop, not SA JSON key).
   - **Authorized redirect URIs** — must match the **current** proxy exactly:

```
https://<POD_ID>-8888.proxy.runpod.net/api/drive/oauth/callback
```

Example for the snapshot Pod above:

```
https://4favaamr1akoda-8888.proxy.runpod.net/api/drive/oauth/callback
```

5. Copy Client ID + Client secret into `/workspace/secrets/drive-oauth.env` (and set `VARIANT_DRIVE_OAUTH_REDIRECT_URI` to the same URI).
6. Enable **Google Sheets API** (same project) — required for the Drop Ledger.
7. Restart Studio so `variant-server` inherits the env (`bash /workspace/start-varyforge.sh` or redeploy script below).

Mismatch of redirect URI (Console vs env vs actual proxy host) is the most common Connect Google failure.

---

## Drop Ledger (platform Passed / Rejected labels)

Durable Google Sheet that survives Pod wipes. Labels here are **training data for a future
preset/escalate bias** — there is **no auto-tune yet**.

| Item | Value |
|------|--------|
| Sheet title | `VaryForge Drop Ledger` |
| Config (on Pod, not committed) | `/workspace/vmdata/drive/drop_sheet.json` or env `VARIANT_DROP_SHEET_ID` |
| Ensure | `POST /api/drop-ledger/ensure` |
| Sync (upsert by job_id+variant_id) | `POST /api/drop-ledger/sync` with optional `{"job_ids":["…"]}` |
| Status | `GET /api/drop-ledger/status` |

**OAuth:** Connect Google must include **Spreadsheets** scope. After deploy, open
**Settings → Drive → Connect Google** (reconnect once) so the new scope is granted.

**How VAs label today**

1. Prefer Gallery → open variant → **Passed upload** / **Duplicate rejected** (writes
   `platform_result` locally + updates the Sheet row when ledger is configured).
2. Or edit the Sheet `platform_result` column directly:
   `passed` \| `duplicate_reject` \| `flagged` \| `unknown` (blank = unlabeled).

**Seed recent jobs (example)**

```bash
curl -sS -X POST http://127.0.0.1:8000/api/drop-ledger/sync \
  -H 'Content-Type: application/json' \
  -d '{"job_ids":["b9b359a18d3b","bc11837cc38a"],"ensure":true}'
```

---

## After Pod migration checklist

When SSH host/port or proxy URL changes:

1. Note new SSH: `root@<IP> -p <PORT>` and new UI `https://<NEW_POD_ID>-8888.proxy.runpod.net`.
2. Redeploy / start app (rsync + install, or `bash /workspace/start-varyforge.sh`).
3. Update **Authorized redirect URI** in Google Console to the new callback URL.
4. Update `VARIANT_DRIVE_OAUTH_REDIRECT_URI` in `/workspace/secrets/drive-oauth.env`.
5. Restart so env is loaded.
6. **Settings → Drive → Connect Google** again if the token is missing or auth fails (network volume may keep the old token; reconnect if needed).
7. Confirm destinations still work (folder write probe).

**Network volume note:** a RunPod network volume can keep `/workspace` install + `vmdata` (including OAuth token and destinations) across Pods. **Proxy URL and SSH host/port still change** — redirect URI + Console must be updated even when the volume is reused.

---

## VA / operator usage

1. Open the current proxy UI URL.
2. **Settings → Drive**
3. **Connect Google** (admin once, company account) if not connected.
4. **Add destination** — friendly name + paste a Drive folder link the connected account can edit.
5. **Gallery** — select finished `ok` variants → **Send to Drive** → pick destination → watch export progress / retry failures if shown.

**Disconnect** clears the refresh token on the Pod (Settings → Drive).

---

## Redeploy helper

From a Mac with SSH access to the Pod:

```bash
# Defaults in the script may lag the live Pod — override host/port:
POD_HOST=root@213.192.2.76 POD_PORT=40036 bash deploy/pod/redeploy-oauth.sh
```

Script: [`deploy/pod/redeploy-oauth.sh`](../../deploy/pod/redeploy-oauth.sh)

It rsyncs the repo, installs `.[server,farm]`, builds the web UI, sources `/workspace/secrets/drive-oauth.env` if present, and restarts via `deploy/pod/start.sh`. Prefer the Pod’s `start-varyforge.sh` wrapper when that is the documented local restart path.

---

## Quick health checks (on Pod)

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/drive/status
```

Expect Drive status to show connected / ready after OAuth env + Connect Google — not “not configured”.

---


---

## ComfyUI / Create Mode on this Pod

Studio **Create** UI talks to local Comfy InstantID (deploy from **`create-mode`**).

| Item | Value |
|------|--------|
| Studio Create | `https://<POD>-8888.proxy.runpod.net/create` |
| Install | `bash /workspace/variant-maker/deploy/comfy/bootstrap.sh` |
| Models | `/workspace/comfy-models` (SDXL + InstantID + antelopev2) |
| Listen | `127.0.0.1:8188` only — do **not** expose via RunPod HTTP proxy |
| API → Comfy | `COMFY_URL=http://127.0.0.1:8188` (set in `deploy/pod/start.sh`) |
| Workflow | `COMFY_WORKFLOW_PATH=.../deploy/comfy/workflows/create_instantid_sdxl.json` |
| Health | `curl -fsS http://127.0.0.1:8188/system_stats` |
| GPU | Sequential with Spoof HQ — pin `CUDA_VISIBLE_DEVICES=0` when multi-GPU |

See also `docs/ops/create-mode-comfy.md` on the create-mode branch.

## Do not

- Commit real client IDs, secrets, or `oauth_token.json`.
- Use a service-account JSON key as the primary path when org policy blocks key download.
- Leave an old redirect URI in Google Console after the proxy host changes.
