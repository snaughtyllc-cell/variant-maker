# VaryForge on RunPod (always-on Pod)

Simplest path for you + VAs: one Pod, one URL, upload → variants → download.

This uses **Tier-1 (FFmpeg/CPU)**. An RTX 4000 works fine; GPU neural upscale is optional later.

---

## Option A — existing Pod (fastest, recommended)

1. Start / connect to your Pod (Jupyter or SSH terminal).
2. Paste:

```bash
curl -fsSL https://raw.githubusercontent.com/snaughtyllc-cell/variant-maker/tier1/deploy/pod/bootstrap-on-pod.sh | bash
```

Or if `curl | bash` is blocked:

```bash
cd /workspace
git clone --branch tier1 --depth 1 https://github.com/snaughtyllc-cell/variant-maker.git
bash variant-maker/deploy/pod/bootstrap-on-pod.sh
```

3. In the RunPod UI: **Connect → HTTP service → port `3000`**.
4. Share that URL with VAs (treat it like a password — no login yet).

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
