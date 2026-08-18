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

Until RunPod + object-store env is set, Studio still works: the start script
falls back to `--runner local` and renders on Railway CPU (Tier 1).

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

Control-plane HQ defaults stay on the GPU worker (`quality_mode=hq`). Uniqueness
gate + one creative escalate are forwarded in the job payload.

## 4. Drive OAuth

Google Cloud → Web OAuth client → authorized redirect URI:

```
https://<railway-domain>/api/drive/oauth/callback
```

Set `VARIANT_DRIVE_OAUTH_*` on Railway (see `deploy/railway/studio.env.example`).
Studio → Settings → Drive → Connect Google.

## 5. Team use

Share the Railway URL. One login is enough (no multi-user accounts yet). Treat
the URL like a password until you add auth.
