# Shared Studio live queue (no logins)

**Date:** 2026-08-20  
**Status:** Shipped.  
**Product name:** VaryForge

Jeff + VAs + partner share one public Studio URL. No logins yet. Two people
hitting Generate from different places must not mix files, and anyone about to
Generate should see who is already running — filenames and Fast/HQ progress,
not the video.

## Isolation (already true; keep it)

- Each Generate is its own `job_id` + folders under `/data`. Packs do not
  overwrite each other.
- Fast CPU workers run **in parallel**. Do not serialize Fast into one line —
  that is the long wait we are avoiding.
- HQ stays one-at-a-time on the 4090. A second HQ waits at RunPod.
- Cancel / Gallery remove is **per pack**. Removing a live pack stops that
  Generate for everyone on this URL — confirm copy says so.

## Live queue

`GET /api/queue` lists `state=running` jobs, oldest first:

- `filenames`, Fast vs HQ, `delivered/requested`, `position`
- no variant URLs / no video bytes

Studio shows a card on Generate and a nav pill (`1 gen · Fast 3/8`). Fast copy
says **yours still starts now**. HQ copy says **waits on the GPU** when another
HQ is already going.

## Not this

- Logins / per-user workspaces
- A global Fast lock
- Always-on workers
- Showing someone else's video in the queue
