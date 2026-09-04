# Pipeline hosting — Railway coordinates, objects carry bytes

Railway Studio is a **processing coordinator**, not a video host. Object
storage (R2/S3), RunPod, and Google Drive carry MP4 and ZIP bytes.
Railway keeps auth, billing, job status, and metadata.

Lab (`snaughtyllc-cell/variant-maker`) and Live (`snaughtyllc-cell/varimo-live`)
stay separate GitHubs. Promote chosen files with `scripts/promote-to-live.sh`.
Do not `git merge` Lab ↔ Live. See [`two-githubs.md`](two-githubs.md).

## Flows

```text
Manual
  Browser → signed PUT to object storage
         → RunPod downloads source
         → RunPod writes variants to object storage
         → customer GET via short-lived signed URL

Google Drive
  Drive file id + job-scoped access token
         → RunPod downloads source
         → RunPod writes variants to object storage
         → RunPod uploads to Drive (deliver_drive)
         → Railway records completion
```

Railway handles: authentication, job create/status, billing, short-lived
links, source/output metadata, RunPod submit + cancel + callbacks.

Railway does **not** handle ordinary MP4 playback, MP4/ZIP downloads through
the web service body, range streaming, copying completed files onto `/data`,
or relaying Drive exports through the application volume.

## Telemetry (every job)

Persisted on `job.json` and copied onto `{workspace}/usage.jsonl`:

- workspace, requested count, processing charge (`Fast 20 pack`)
- RunPod job id, endpoint id, submit/start/complete/shutdown
- retry + regen counts, input/output bytes
- delivery destination, output expiry, estimated RunPod USD
  (`VARIANT_RUNPOD_FAST_USD_PER_HOUR`, default `$0.58`)

## Object storage

Browser `POST /api/uploads/direct` → `mode=direct` + signed PUT (or
`mode=local` fallback). Jobs start with `POST /api/jobs/from-object`.

Downloads: `GET /api/sources/{id}/downloads` returns signed URLs.
`GET /api/variants/...` and `/zip` **302** to object storage when the file
is not on disk.

**R2 CORS** must allow `PUT` and `GET` from the Studio origin
(production: `https://varyforge-studio-production.up.railway.app`).

Retention: metadata 7 days (`VARIANT_GALLERY_KEEP_HOURS`). Output MP4s 48h
(`VARIANT_OUTPUT_KEEP_HOURS`, 24–72h window). Drive-delivered objects expire
after ~1h once upload is confirmed.

## Gallery

Pack list and tiles use JPEG look posters (`look_var_url` / `poster_url`).
Opening Gallery or Studio must not request MP4s. The variant sheet still
plays a file on explicit open (302 → object storage).

## Drive tokens

RunPod never receives the Google refresh token. Railway mints a short-lived
access token per job (`drive_tokens.mint_access_token`).

## RunPod Fast endpoint (dashboard, not code)

Current production: min workers 0, max 4, idle timeout **600s**, ~$0.58/hr.

**Trial:** drop idle timeout to **30–60 seconds** on the Fast CPU endpoint.
Confirm cold-start is acceptable. Keep HQ off until separately benchmarked.
`VARIANT_RUNPOD_MAX_SECONDS` (default 3600) is the per-job execution cap.

Resume failure **does not** submit a second RunPod job. Cancel POSTs
`/cancel/{id}` on the bound RunPod request.

## Acceptance

- Ordinary MP4/ZIP bytes do not pass through the Railway web service.
- Jobs / Gallery pages issue no automatic `<video>` requests.
- Direct downloads are short-lived object URLs.
- Drive export does not copy files onto the Railway volume.
- One RunPod request maps to one Varimo job.
- Duplicate resume cannot create another charge.
- Seven-day Railway egress should drop after Live promote + deploy.
