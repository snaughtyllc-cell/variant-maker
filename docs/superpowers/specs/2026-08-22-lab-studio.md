# Lab Studio (full copy, live stays still)

**Date:** 2026-08-22  
**Product name:** VaryForge  
**Depends on:** `2026-08-21-lab-prod-split.md`, `docs/ops/lab-fast.md`

## Why

Jeff: the testing side is a **complete usable lab**. Live Studio keeps the
last thing we put on it. Experiments never touch the working box — not the
Fast workers the team generates on, not the Gallery they watch, not a
Railway restart to hydrate a lab pack.

v0 already split **Fast CPU** (live `j0b1q4iuunzhnq` vs lab
`xar25v77v3j27u`). The hole: lab packs were written into the **production**
tenant volume and production Studio was restarted so Gallery showed them.
That is the working product.

## Two Studios

| | **Live** (team) | **Lab** (Jeff + agent) |
|---|---|---|
| URL | `varyforge-studio-production.up.railway.app` | `varyforge-studio-lab.up.railway.app` (`lab` env `82d2541b-…`) |
| Volume | production `/data` (Drive, Watch, galleries) | **new empty volume** |
| Fast | live digest-pinned endpoint | lab endpoint (`VF_LAB=1`) |
| HQ | existing 4090 | same GPU for v1 (idle $0) |
| Who deploys | promote only | experiment branches |
| Banner | none | `VARIANT_LAB=1` → “LAB — experiments only” |

Lab is a **new empty workspace** on first login, not a clone of Jeff’s
live gallery. Generate on lab hits lab Fast. Generate on live never does.

## Do not

- Set production `RUNPOD_FAST_ENDPOINT_ID` to the lab id
- Mount the production volume on lab
- `railway restart` / `railway up` production to show a lab pack
- Write lab `job.json` into `tenants/ws_*` on the live volume
- Recycle live Fast workers to test a digest
