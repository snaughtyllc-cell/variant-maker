# Drive Farm + Control Plane — Design (2026-06-27)

Status: **approved design, implementation deferred until after Tier 1 ships.**
This captures decisions from the brainstorm so the engine is built with the right seams.

## Goal
Turn variant-maker from a tool you run into a **hands-off, per-client variant farm**: client
videos land in a Google Drive folder, the system pulls each new one, makes variants, and pushes
them back to that client's output Drive — each source video in its own output subfolder — running
on a timer without manual work. Ties into the "B" north star (see PLAN.md / memory): the engine
auto-tunes each variant toward a similarity target above a quality floor.

## Three layers (build inside-out)
1. **Engine** — `variant-maker`, the local renderer (one video → N variants + manifest). *In progress (Tier 1).*
2. **Farm worker** — headless automation around the engine: pull from Drive → render → push back → ledger. *Tier 3.*
3. **Control plane (UI)** — cloud web app for staff/team to manage clients, recipes, folders, and watch runs. *Tier 4. Architecture-level only here; screens designed when we get there.*

The UI sits ON TOP of the worker — it manages config and shows status; the worker still renders.

## Sequencing
**Engine → Worker → UI.** Each layer is a management surface over the one below, so nothing is
built before the thing it manages exists. Worker + UI are built after Tier 1 (Phase 7) ships.

---

## Layer 2 — Farm worker (detailed)

### Decisions (locked)
- **Auth:** a Google **service account** ("robot" account) — no interactive login, runs on a timer.
- **Folder identity:** folders referenced by **Drive folder ID**, ownership-agnostic.
  - **Primary (Option 1):** folders live in a Drive *you* own; you share a client's input folder with them.
  - **Supported (Option 2):** a client/friend keeps folders in their own Drive and shares them with the robot's email. Same machinery, no extra code.
- **Recipe:** **global default + per-client override** (preset, count, platform, quality).
- **Trigger:** **cron poll** — `variant-farm run` does ONE idempotent sweep and exits; an external
  scheduler runs it every `poll_minutes`. No daemon, no message queue (honors the local-CLI scope spirit).
- **Output organization:** per source video → its own output subfolder `<source-stem>__<sha8>/`
  containing the N variants + `manifest.json`.
- **Idempotency:** a **ledger keyed on the source video's sha256** (the engine already computes it).
  Same bytes never reprocessed, even if renamed. Ledger stores: sha → {status done|failed,
  output_folder_id, variant_count, error?, attempts, ts}.
- **Failure handling:** per-video isolation — a bad file is logged, marked `failed` (retried a few
  sweeps, then left), and the rest continue. Each sweep writes a summary (new/done/failed/skipped).
- **Notifications:** Slack/email-on-batch-done is a later optional hook, off by default.
- **Packaging:** optional `[farm]` dependency group (`google-api-python-client`, `google-auth`),
  lazy-imported — the engine stays light and offline-capable, mirroring the neural tier.

### Components (small, single-purpose)
- `farm/config.py` — load clients config (global defaults + per-client overrides + folder IDs + key path).
- `farm/drive.py` — the ONLY Google-aware module: list / download / create-folder / upload, behind an interface.
- `farm/ledger.py` — processed-set keyed on source sha256 + statuses.
- `farm/runner.py` — the sweep: per client → list input → for each new video → download → `pipeline.run` → make output subfolder → upload variants + manifest → update ledger → cleanup.
- `farm/cli.py` — `variant-farm run` (one sweep).

### Config contract (worker input)
```yaml
auth:    { service_account_json: ./secrets/variant-bot.json }
defaults:{ preset: medium, count: 10, platform: reels, quality: fast }
poll_minutes: 15
clients:
  logan:
    input_folder_id:  "1AbC..."
    output_folder_id: "1XyZ..."
    preset: strong        # override
    count: 20
```

### Testing
Drive lives behind one interface → the whole runner is tested with a **fake Drive** + the real
engine: new file → N variants in the right subfolder + ledger updated; already-done → skipped;
failure → marked failed + others continue. No real Google in tests.

---

## Layer 3 — Control plane / UI (architecture only)

**The architectural constraint:** a lightweight cloud web app and heavy video rendering (ffmpeg now,
GPU later, minutes per job) **cannot be the same process.** Split:
- **Control plane** — UI + small database + login + Drive auth. Lightweight, cloud-hosted
  (Next.js on Vercel is the natural fit). Holds clients, recipes, the job list, and run history.
  Becomes the **source of truth** that generates the worker's config contract.
- **Worker** — the Python engine + ffmpeg, runs where it has muscle (container/VM; GPU box for Tier 2).
  Picks up **pending jobs from the DB** (same poll philosophy — no Redis) and reports status back.

### Deployment decision (2026-06-27): serverless GPU for the neural worker
- **Chosen:** serverless GPU (Modal / RunPod serverless / fal.ai / Replicate) over an always-on
  rented GPU VM. A variant farm is bursty — pay per GPU-second, scale to zero, no idle cost.
- **The worker is a Linux x86 GPU CONTAINER build, NOT the local macOS binary.** The mac
  `realesrgan-ncnn-vulkan` will not run on a Linux NVIDIA VM. Production image needs: a Linux
  upscaler build (Linux `realesrgan-ncnn-vulkan` with NVIDIA/Vulkan drivers, OR PyTorch
  Real-ESRGAN on CUDA — likely the more robust NVIDIA path), ffmpeg installed, model weights
  baked/cached into the image, and the Drive pull/push + job handoff wired in.
- **What ports as-is:** the Python orchestration (probe/sampler/filtergraph/render/guard/
  `upscale_clip` logic) is platform-agnostic. Only the GPU runtime is a container/ops build.
- Production picture: **Vercel control plane → Linux GPU container on serverless GPU → results to Drive.**
- Cloud NVIDIA (T4/L4/A10) is far faster than the local M1 (~60–90s upscale → seconds).

UI specifics (screens, roles/permissions, Drive OAuth onboarding flow) are deliberately **deferred**
until the worker exists — they are the most likely to churn and the least useful now.

---

## Engine seams to preserve NOW (so Tier 3/4 aren't boxed out)
1. `pipeline.run(...)` must be a **clean callable** returning structured results (manifest object +
   output file paths + per-variant status), not just a CLI side effect. The worker calls it directly.
2. **sha256 of the source** stays in the manifest (idempotency key for the ledger).
3. **Deterministic, collision-safe output naming** (`<stem>_vNN_<hash>.mp4`) so uploads map cleanly.
4. The engine stays **local + dependency-light**; all Drive/cloud deps live in the optional farm layer.
5. Clear **exit status / error surfacing** per variant so the worker can mark ledger failures precisely.

## Out of scope (YAGNI)
No message queue / Redis, no realtime Drive webhooks (poll is enough), no account-proxy logic, no
DB inside the engine, no UI detail until the worker is real.
