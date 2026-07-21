# VaryForge on RunPod (always-on Pod)

Simplest path for you + VAs: one Pod, one URL, upload → variants → download.

This uses **Tier-1 (FFmpeg/CPU)**. An RTX 4000 works fine; GPU neural upscale is optional later.

---

## Google Drive export (OAuth — recommended)

Service-account JSON keys are often blocked by org policy. Prefer a **Web OAuth client**
(not an SA key) and Connect Google once in Studio Settings.

### 1. Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/) → select/create a project.
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **APIs & Services → OAuth consent screen**
   - User type: **Internal** (Workspace) or **External** (then add test users).
   - App name: e.g. `VaryForge Studio`
   - Scopes: add Drive (`.../auth/drive` and/or `.../auth/drive.file`).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**
   - Name: `VaryForge Pod`
   - **Authorized redirect URIs** — add exactly:

```
https://li25cvxk21j8jn-8888.proxy.runpod.net/api/drive/oauth/callback
```

   (If the Pod proxy host changes, update this URI and `VARIANT_DRIVE_OAUTH_REDIRECT_URI`.)

5. Copy the **Client ID** and **Client secret**.

### 2. Pod environment

On the Pod (or in the start script / systemd unit), export:

```bash
export VARIANT_DRIVE_OAUTH_CLIENT_ID="….apps.googleusercontent.com"
export VARIANT_DRIVE_OAUTH_CLIENT_SECRET="…"
export VARIANT_DRIVE_OAUTH_REDIRECT_URI="https://li25cvxk21j8jn-8888.proxy.runpod.net/api/drive/oauth/callback"
# Optional fallback if you still have an SA key:
# export VARIANT_DRIVE_SERVICE_ACCOUNT_JSON=/workspace/secrets/drive-sa.json
```

Also install the farm extra if missing: `pip install -e '.[farm]'` (needs `google-auth-oauthlib`).

Token file (created after Connect Google): `/workspace/vmdata/drive/oauth_token.json`  
Do **not** commit this file.

### 3. Connect in the UI

1. Open `https://li25cvxk21j8jn-8888.proxy.runpod.net/settings/drive`
2. Click **Connect Google** → complete consent as the company Drive account
3. Confirm “Connected as …” and email
4. Add destinations (paste folder links the signed-in account can edit)
5. Gallery → select ok variants → **Send to Drive**

**Disconnect** clears the refresh token on the Pod.

### 4. Restart notes

After setting env vars, restart API + UI (re-run `deploy/pod/start.sh` or kill/restart
`variant-server` + `next start`). Env must be present in the process that runs
`variant-server` — setting them only in a shell that then exits does nothing.

---

## Option A — existing Pod (fastest, recommended)

Repo is private, so clone with a GitHub token (or upload the folder). In the Pod terminal:

```bash
cd /workspace
# If prompted for a password, paste a GitHub Personal Access Token (not your account password)
git clone --branch tier1 --depth 1 https://github.com/snaughtyllc-cell/variant-maker.git
bash variant-maker/deploy/pod/bootstrap-on-pod.sh
```

Then in the RunPod UI: **Connect → HTTP service → port `3000`**.
Share that URL with VAs (treat it like a password — no login yet).

Expected URL shape:

`https://<POD_ID>-3000.proxy.runpod.net`

### Template tip (so it auto-starts next time)

In Pod template / start command:

```bash
bash /workspace/variant-maker/deploy/pod/bootstrap-on-pod.sh
```

Expose **TCP port 3000** (HTTP).

---

## Option B — Docker image

On an amd64 builder (or the Pod itself):

```bash
docker build -f deploy/pod/Dockerfile -t variant-maker-pod .
docker run --rm -p 3000:3000 -v /workspace/vmdata:/workspace/vmdata variant-maker-pod
```

---

## VA usage

1. Open the proxy URL
2. Upload a short clip (5–60s)
3. Pick count + preset (`subtle` ≈ Safe, `medium` ≈ Balanced, `strong` ≈ Creative)
4. Generate → Gallery → download

---

## Uniqueness smoke (after pull)

This Pod template exposes HTTP on **7860** (not 3000). In RunPod Connect, use **HTTP service → port `7860`**.

1. Start pod services (`WEB_PORT=7860`)
2. Open the proxy URL (`https://<POD_ID>-7860.proxy.runpod.net`)
3. Generate 3 variants **Light**
4. Confirm uniqueness scores in Gallery
5. Mark one **Passed** / one **Duplicate rejected**
6. Download ZIP

RunPod HTTP proxy may still buffer SSE; job-detail polling shows progress reliably. Stop the Pod when idle.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| Port “initializing” forever | Confirm process listens on `0.0.0.0:3000` (`ss -lntp \| grep 3000`). Start script does this. |
| UI loads, Generate fails | API not up — check logs for `variant-server` / `/api/health`. |
| `libvmaf` errors | Bootstrap installs johnvansickle static ffmpeg; re-run bootstrap. |
| Clone is old / missing UI | Need latest `tier1` on GitHub (`git push`). |
| Pod restarted, app gone | Put bootstrap in the template start command; keep `/workspace` volume. |

---

## Not this path

- `deploy/runpod/` = serverless GPU farm (R2 + Drive). Heavier. Use later for scale.
- `~/vidforge*.py` stubs = ignore.
