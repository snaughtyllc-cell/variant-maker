# Codex prompt — deploy VaryForge Studio to Railway

Paste the block below into Codex (it already has Railway auth). After it
returns a public URL, we wire RunPod serverless + object storage.

---

You are deploying **VaryForge Studio** (repo `snaughtyllc-cell/variant-maker`)
to Railway. Use the current git branch (or `cursor/railway-runpod-split-c975`
if you are not already on it).

## What to deploy

One Railway **service** from the repo root using the Dockerfile:

- Builder: **DOCKERFILE**
- Dockerfile path: `deploy/railway/Dockerfile`
- `railway.toml` in the repo already sets this.

This image is **CPU-only**: Next.js UI + FastAPI (`variant-server`). It listens
on `$PORT` (mapped in `deploy/pod/start.sh`). Health check: `GET /api/health`.

Do **not** enable application sleep.

## Steps

1. Create or reuse a Railway project named `varyforge-studio` (or similar).
2. Deploy this directory (`railway up` / Dockerfile builder as above).
3. Add a **volume** mounted at `/data`.
4. Set service variables:
   - `DATA_DIR=/data/vmdata`
   - Do **not** set `VARIANT_RUNNER` yet (start script defaults to `local` until RunPod env exists).
5. Generate a public HTTPS domain.
6. Confirm `/api/health` returns `{"status":"ok"}` on that domain.
7. Reply with:
   - project id / service id / environment
   - public URL
   - volume mount confirmation
   - any build/runtime errors (verbatim)

## Out of scope for this pass

- Do not create a GPU service on Railway.
- Do not set `RUNPOD_*` or `R2_*` unless those secrets are already in the Railway project.
- Do not print or commit secrets.

When this is green, the team can open the URL and Generate on Railway CPU.
RunPod serverless is a later env-var flip (`VARIANT_RUNNER=runpod`).
