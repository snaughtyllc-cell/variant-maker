# Codex prompts — RunPod serverless engine + Drive OAuth

Studio is already live:

https://varyforge-studio-production.up.railway.app

This Cursor cloud agent **cannot** create the RunPod endpoint or set Railway
secrets (no RunPod key, no Railway token, no Docker). Paste these in order into
**Codex** (Railway + the GPU pod). Reply here with the endpoint id when Prompt A
and B are done — do not paste API keys.

Team UX: Telegram-style “upload → start → done” is a **warm GPU**, not scale-to-zero
magic. Endpoint settings below copy that: FlashBoot on, **idle timeout 10 min**
(so the next clip does not cold-start), active workers 0 overnight / 1 if you
want zero wait, `VARIANT_QUALITY_MODE=fast`.

## How long a boot actually takes

| Situation | What you feel |
|---|---|
| **True cold start** (image pull, CUDA, our fat Real-ESRGAN image, min workers = 0, no FlashBoot snapshot) | **~30s–2+ min** before the first frame encodes. Our worker image is large. |
| **FlashBoot restore** (same host still has a snapshot) | **~0.2–8s** in RunPod’s published numbers. Not guaranteed if they schedule a new host. |
| **Active workers = 1** (GPU already up) | **0 boot.** Generate time is only encode + uniqueness (seconds to a couple minutes per batch). |
| Default **idle timeout = 5s** | Worker dies between clips. Every VA job looks “slow” even after the first. **Do not ship this.** |

Those Telegram bots are not running one GPU that sleeps. They keep a **pool of warm workers** (or idle timeout long enough that the next upload hits a live box). We do the same at team scale: one worker that stays up while people are dropping files.

**Do not build a “Turn GPU on + countdown” as the main path.** Extra click, people forget, first Generate still waits. Better:

1. **Open Studio / drop a file** → we ping the endpoint (warmup overlaps with picking files). Later UI work; not required if idle timeout is 10 min and someone already generated once.
2. Optional night switch: active workers **0** after hours, **1** during the workday (or a Start GPU control for that). First person in the morning waits one cold start; everyone after is instant.

Overnight with active workers = 0 you pay **$0 GPU**. Daytime with 1 warm worker you pay GPU-hours, but **not** a Studio-on-GPU pod, and VAs get the Telegram feel.

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
   - GPU: **RTX 4090 / L40S** (~$1–2/hr while running). Proven path is 4090.
     Skip L4 if HQ should feel faster. **Do not** pin Blackwell PRO 6000 MIG (`sm_120`).
     Min/active workers stay **0** (or 1 only during a work session). A $2 card does
     not 20× a serial HQ batch; raise **execution timeout** (e.g. 3600s) only for
     HQ experiments, not as the way to ship 20 HQ variants.
   - **FlashBoot: on**
   - **Active / min workers: 1** for VA hours (0 boot). Use 0 only if you accept a
     first-job wait after idle.
   - **Max workers: 2**
   - **Idle timeout: 600 seconds** (10 min). Default 5s will cold-start every clip.
   - **Execution timeout: 1200 seconds** (a batch can exceed 10 min).
   - Endpoint env (same R2_* as Railway):
     `R2_ENDPOINT`, `R2_BUCKET`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`
4. Reply with: image tag, endpoint **id**, GPU type, min workers, idle timeout.
   **Do not paste the API key.**

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
