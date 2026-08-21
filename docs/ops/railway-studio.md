# VaryForge Studio on Railway + RunPod serverless

Railway hosts the **product** (Studio UI + `variant-server`). RunPod serverless
hosts the **engine** (ffmpeg + optional HQ GPU). Object storage is the mailbox
between them.

```
Team browser
  → Railway  (Next.js + variant-server, CPU, cheap)
        → uploads, gallery, Drive OAuth
        → RunPod serverless  (render; $0 idle)
        → R2 / S3 / Railway bucket
        → Railway downloads variants into the gallery
```

Studio is live at https://varyforge-studio-production.up.railway.app

Until RunPod + object-store env is set, Studio still works: the start script
falls back to `--runner local` and renders on Railway CPU (Tier 1). That path is
too slow for VA in-and-out. Use RunPod serverless with **min workers = 0**,
**idle timeout ~10 min**, `VARIANT_QUALITY_MODE=fast` (see
[`codex-runpod-and-drive.md`](codex-runpod-and-drive.md)).
Overnight GPU is $0; a warm window after the last job costs GPU-hours only while
that worker is still up. Prefer a **4090-class** card (~$1–2/hr while running) over
L4 for HQ; **min workers stay 0**. HQ is still one variant at a time — do not expect
20 HQ files in a few minutes from GPU class alone.

## 1. Railway (Codex can do this)

Paste [`codex-railway-deploy.md`](codex-railway-deploy.md) into Codex. It should:

1. Deploy this repo with `deploy/railway/Dockerfile`.
2. Attach a volume at `/data`.
3. Set `DATA_DIR=/data/vmdata`.
4. Generate a public HTTPS domain.
5. Print the URL.

Do **not** enable app sleep while Generate jobs can be in flight.

## 2. Object storage

Any S3 API works. Cloudflare R2 (zero egress) is the default in code (`R2_*` env
names). A Railway bucket is also S3-compatible — map its credentials to:

- `R2_ENDPOINT`
- `R2_BUCKET`
- `R2_ACCESS_KEY`
- `R2_SECRET_KEY`

Set the **same** four vars on the RunPod serverless endpoint.

## 3. RunPod serverless (engine)

Build on **amd64/NVIDIA** (not a Mac):

```bash
docker build -f deploy/runpod/Dockerfile -t <registry>/variant-cp:latest .
docker push <registry>/variant-cp:latest
```

Create a RunPod **serverless** endpoint from that image. Override the start
command (the image default is the Drive-farm handler):

```
python -u /app/deploy/runpod/cp_handler.py
```

Endpoint env: `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`.

Then on Railway set `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY`, the four `R2_*`
vars, and `VARIANT_RUNNER=runpod` (or omit `VARIANT_RUNNER` — auto-selects
runpod when those vars are complete). Restart the Railway service.

### 3b. Fast CPU worker (scale to zero)

Fast 20-packs should **not** wake the 4090. CI builds
`ghcr.io/snaughtyllc-cell/variant-fast:latest` from
`deploy/runpod/Dockerfile.fast` (ffmpeg+libvmaf, no CUDA). Create a second
RunPod **CPU** serverless endpoint from that image:

- Compute type: **CPU**. Instance with **8+ cores** (e.g. `cpu3g-8-32`).
- Start command is already `python -u /app/deploy/runpod/cp_handler.py`.
- Min workers **0**, max workers 1–2, idle timeout **600s**, FlashBoot on.
- Execution timeout **3600s** (a 20-pack must not die at 10–20 min).
- Same `R2_*` env as the GPU endpoint.

Set `RUNPOD_FAST_ENDPOINT_ID` on Railway to that endpoint id. Until it is set,
Fast 20s still use the GPU endpoint. HQ always uses `RUNPOD_ENDPOINT_ID`.

Control-plane HQ defaults stay on the GPU worker (`quality_mode=hq`). Uniqueness
gate + one creative escalate are forwarded in the job payload.

## 4. Drive OAuth

Google Cloud → Web OAuth client → authorized redirect URIs:

```
https://varyforge-studio-production.up.railway.app/api/drive/oauth/callback
https://varyforge-studio-production.up.railway.app/api/auth/google/callback
```

Set `VARIANT_DRIVE_OAUTH_*` on Railway (see `deploy/railway/studio.env.example`).
Studio → Settings → Drive → Connect Google.

## 5. Team use (invite-only workspaces)

One public URL. Auth is **off** until `VARIANT_AUTH_ADMIN_EMAIL` is set (today’s
open Studio). To give each operator their own gallery + Drive:

1. Add the login callback URI above to the Google OAuth client.
2. Set on Railway:
   - `VARIANT_AUTH_ADMIN_EMAIL` — your Google email
   - `VARIANT_AUTH_SECRET` — a long random string (or omit and Studio writes
     one to `{DATA_DIR}/auth/secret` on first boot)
3. Redeploy, open Studio, sign in with **email + password** (first visit sets
   the password) or **Continue with Google**. First admin login moves
   existing packs into your workspace.
4. **Admin** in the top nav (site admin only):
   - **Join my workspace** — VAs land in your gallery (shared on purpose).
     Tell them: Studio URL → invited email + a password they choose (or
     Google). First password sign-in sets it.
   - **New workspace** — outside operators get an empty studio + their own
     Drive Connect.
   - **Open** on a row — you see their Studio (gallery, queue, Generate,
     Drive) with a **Viewing {name} — Exit to your studio** banner. Exit
     returns you home.
   - **Remove** on a member — they cannot sign in until you invite them
     again. Workspace files stay. You cannot remove your own admin login.
5. **Team** in the top nav (workspace owners, including those new-workspace
   operators): invite a VA into *this* studio. Same join-invite as Admin
   “Join my workspace,” without creating a new empty studio. They can
   Remove their own members. They cannot mint `new_workspace` invites.

Non-admins never see the Admin page or anyone else’s packs. Uninvited emails
get “ask the operator to add you.” Invited people can use email + password
or Google.

**Platform flags:** Gallery can mark Passed / Duplicate rejected / Flagged
(`platform_result`). Unlabeled clips count as pass. Drop Ledger (Google Sheet)
is the durable log — see §6.

## 6. Drop Ledger (`VARIANT_DROP_SHEET_ID`)

A Google Sheet named **VaryForge Drop Ledger** stores Passed / Duplicate
rejected / Flagged per clip so labels survive Pod wipes. It does **not**
auto-tune uniqueness.

**Operators (Jeff / VAs)**

1. Studio → **Settings → Drive → Connect Google** (must allow Google Sheets).
2. **Ensure sheet** — creates the sheet if it is missing (or uses the pinned id).
3. **Sync from Studio** — writes current jobs into the sheet. Labels already in
   the sheet stay put.
4. Gallery → open a variant → **Passed upload** / **Duplicate rejected** /
   **Flagged**. Unlabeled = pass. Labels write through to the sheet.

**Railway env (optional but recommended)**

```
VARIANT_DROP_SHEET_ID=<spreadsheet id from the sheet URL>
```

If unset, Ensure sheet creates a spreadsheet and stores the id on the volume
(`{DATA_DIR}/drive/drop_sheet.json`). Pin the id so every deploy uses the same
sheet. Enable the **Google Sheets API** on the same Google Cloud project as
Drive OAuth.

This is not a posting tracker (drops board is a later spec).
