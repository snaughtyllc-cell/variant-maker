# Live Studio vs lab (so VAs keep working while we break things)

**Date:** 2026-08-21  
**Status:** Spec only — do not stand up until asked  
**Product name:** VaryForge  
**Depends on:** `2026-08-19-fast-worker-split.md`, `docs/ops/railway-studio.md`

## Why

Live Fast, live Studio, and the agent’s experiment loop are the **same machines**.

Today `cursor/railway-runpod-split-c975` is all of:

- Railway production Studio (`varyforge-studio-production.up.railway.app`)
- GitHub Actions pushing `ghcr.io/snaughtyllc-cell/variant-fast:latest`
- The one Fast CPU endpoint Watch/Generate use (`j0b1q4iuunzhnq`, max 2)
- The volume with Jeff’s Drive ledgers (`/data`)

So every uniqueness experiment that ships:

1. Rebuilds Studio (Watch poller restarts).
2. Rebuilds `:latest` and **recycles Fast workers** (cancels in-flight packs).
3. Occupies the same 1–2 CPU workers the team needs.

That is the thing to stop. Not “never change Fast” — **change it on a lab that nobody else is sitting on**.

## Two spaces

| | **Live** (everyone) | **Lab** (Jeff + agent) |
|---|---|---|
| URL | current production Studio | a second Railway env, different hostname |
| Volume | production `/data` (Drive, Watch, galleries) | **separate** volume. Never Jeff’s ledgers. |
| Fast CPU | endpoint A, digest-pinned, recycle **only on promote** | endpoint B, `:lab` tag, recycle whenever |
| HQ GPU | existing 4090, min 0 | **same endpoint for v1** (GPU is idle $0; CPU is the collision) |
| Who deploys | promote a known-good digest | every experiment branch |

Do **not** split one pack across live+lab. Do **not** send 20-packs to Railway Studio CPU. Min workers stay **0** on both Fast endpoints.

## Cheapest first cut (v0 — Fast only)

Studio stays one URL. The collision is Fast CPU, so split that first.

1. **Stop treating `:latest` as live.** Live Fast stays pinned to a digest (`VF_ENGINE_REV` on the endpoint). Agent recycle of live workers is a promote step, not a PR step.
2. **CI on the working branch pushes `variant-fast:lab`**, not `:latest`.
3. **Second RunPod CPU endpoint** (`varyforge-fast-cpu-lab`), min 0, max 1, same R2 mailbox **or** a lab prefix so files do not land in the live gallery by accident. Prefer a distinct R2 prefix (`lab/`).
4. Lab Studio-or-CLI jobs set `RUNPOD_FAST_ENDPOINT_ID` to the lab id. Live Railway keeps the live id.
5. Promote = PATCH live endpoint image to the lab digest that passed a talking-head pack + a motion pack. Then recycle **live** workers once.

This already lets people Generate while we burn lab CPU.

## Then Studio (v1)

Railway **staging** environment, own domain, own volume, `DATA_DIR=/data/vmdata`.

- Lab Studio → lab Fast endpoint.
- Live Studio → live Fast endpoint. **No `railway up` / volume-swap / `--from-source` on production.**
- Auth can stay the same Google client with a second callback URI, or a Jeff-only allowlist on lab.

Pushing an experiment branch must not auto-deploy production. Disconnect production from `cursor/railway-runpod-split-c975` auto-deploy; production tracks a `live` / `tier1` promote, or “deploy from this image tag only.”

## HQ GPU

Do **not** buy a second 4090 for v0. HQ is serial, min 0, rare. Recycle GPU only when the HQ image itself changes, and say so in the promote notes. Add a lab GPU endpoint later if HQ experiments start knocking VAs off the 4090.

## Success

- A VA 8-pack on live Fast is never cancelled because an agent recycled workers to test crop.
- Watch on production survives engine PRs.
- Jeff can still hop on a lab URL and see the next uniqueness recipe before anyone else does.
- Overnight both Fast endpoints still scale to $0.

## Do not

- Encode lab jobs on the live Fast endpoint
- Share the production volume with lab
- Raise uniqueness gates or clone Pixel AI as part of this split
- Leave lab Fast `max` high enough to race live on the same RunPod account quota without watching it
