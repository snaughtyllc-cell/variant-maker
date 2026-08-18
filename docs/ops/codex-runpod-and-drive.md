# Codex prompts — RunPod serverless engine + Drive OAuth

Studio is already live:

https://varyforge-studio-production.up.railway.app

This Cursor cloud agent **cannot** create the RunPod endpoint or set Railway
secrets (no RunPod key, no Railway token, no Docker). Paste these in order into
**Codex** (Railway + the GPU pod). Reply here with the endpoint id when Prompt A
and B are done — do not paste API keys.

Team UX: keep **one warm worker** (`min workers = 1`) so Generate is not a cold
start, and `VARIANT_QUALITY_MODE=fast` so the worker matches today’s pod speed
(FFmpeg + uniqueness, not Real-ESRGAN on every clip). HQ is a later flip.

---

## Prompt A — Railway Codex (bucket + later env)

You are operating the existing Railway project that serves
`https://varyforge-studio-production.up.railway.app`.

1. Create an S3-compatible **Railway bucket** in this project (name e.g. `varyforge-media`).
2. Fetch bucket credentials (`railway bucket credentials`). Map them to:
   - `R2_ENDPOINT`
   - `R2_BUCKET`
   - `R2_ACCESS_KEY`
   - `R2_SECRET_KEY`
3. Do **not** set `VARIANT_RUNNER=runpod` until Prompt B returns `RUNPOD_ENDPOINT_ID`.
4. Reply with: project/service ids, bucket name, and the **endpoint URL** (not the secret keys). Keep access key/secret in Railway only.

When Prompt B is done, set these on the Studio service and **restart**:

```
VARIANT_RUNNER=runpod
VARIANT_QUALITY_MODE=fast
RUNPOD_ENDPOINT_ID=<from Prompt B>
RUNPOD_API_KEY=<existing RunPod API key — rotate if it was ever pasted in chat>
R2_ENDPOINT=...
R2_BUCKET=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
DATA_DIR=/data/vmdata
```

The four `R2_*` values must be **identical** on Railway and on the RunPod endpoint.

---

## Prompt B — GPU host / RunPod (build image + serverless endpoint)

Run this on an **amd64 Linux + Docker** machine (the existing VaryForge GPU Pod is fine).
Repo: `snaughtyllc-cell/variant-maker`, branch `cursor/railway-runpod-split-c975` (or `tier1` after merge).

1. `docker build -f deploy/runpod/Dockerfile -t <registry>/variant-cp:latest .`
   Build context = repo root. This image is large (CUDA + Real-ESRGAN weights).
2. `docker push <registry>/variant-cp:latest`
   Use RunPod’s container registry, GHCR, or Docker Hub — whatever this account already uses.
3. Create a RunPod **Serverless** endpoint from that image:
   - **Start command (required — override image CMD):**
     `python -u /app/deploy/runpod/cp_handler.py`
   - GPU: RTX 4090 or similar (proven path).
   - **Min workers = 1** (warm GPU so VAs are not waiting on cold start).
   - Max workers: 1–2 for now.
   - Endpoint env (same R2_* as Railway):
     `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`
4. Reply with: image tag, endpoint **id**, GPU type, min workers. **Do not paste the API key.**

---

## Prompt C — Drive OAuth (after A+B, or in parallel)

Google Cloud project that already has Drive API (used on the old Pod).

1. Credentials → the **Web application** OAuth client (not a service-account JSON key).
2. Add authorized redirect URI **exactly**:

```
https://varyforge-studio-production.up.railway.app/api/drive/oauth/callback
```

Leave the old RunPod proxy URI in the list until that pod is retired.

3. On the Railway Studio service set:

```
VARIANT_DRIVE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
VARIANT_DRIVE_OAUTH_CLIENT_SECRET=...
VARIANT_DRIVE_OAUTH_REDIRECT_URI=https://varyforge-studio-production.up.railway.app/api/drive/oauth/callback
```

If `/workspace/secrets/drive-oauth.env` exists on the old Pod, copy client id/secret from there and **change only the redirect URI**. Do not commit that file.

4. Restart Railway Studio.
5. Open https://varyforge-studio-production.up.railway.app/settings/drive → **Connect Google** as the company Drive account.
6. Add a destination folder the connected account can edit.
7. Confirm `/api/drive/status` shows `oauth` / connected email.

---

## Smoke (after A+B env restart)

1. https://varyforge-studio-production.up.railway.app/api/health → `{"status":"ok"}`
2. Upload a short clip, Generate 3, Light/fast. Progress should move in seconds–minutes on the warm worker, not tens of minutes on Railway CPU.
3. Gallery shows `ok` variants.
4. After Prompt C: Send to Drive on one `ok` variant.
