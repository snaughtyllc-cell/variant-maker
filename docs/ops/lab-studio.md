# Lab Studio

Live Studio is the team product. Lab Studio is a second Railway environment
with its own URL, empty volume, and Fast endpoint. Experiments go there.
Live stays on the last promoted deploy.

| | Live | Lab |
|---|---|---|
| Railway env | `production` `b43c8623-d8a4-4f2c-b1d2-c7f660aca870` | `lab` `82d2541b-e64b-4bf2-9bf0-862b9c0dadfc` |
| URL | https://varyforge-studio-production.up.railway.app | https://varyforge-studio-lab.up.railway.app |
| Volume | `varyforge-studio-volume` `/data` (prod instance, ~2.7 GB) | **same volume name, separate empty instance** |
| Fast | `RUNPOD_FAST_ENDPOINT_ID=j0b1q4iuunzhnq` | `xar25v77v3j27u` |
| HQ | `RUNPOD_ENDPOINT_ID=f0carwe6u9bdd6` | same GPU for v1 (idle $0) |
| Flag | unset | `VARIANT_LAB=1` |
| Watch branch | promote only (`railway up` / pin) | `cursor/lab-studio-c975` |

Lab first login is a **new empty workspace** (new `ws_*` on the empty volume).
Same admin email as live. Set a password on first lab sign-in — it does not
change the live password.

## Rules

- Do **not** point production Fast at lab.
- Do **not** share `/data` with production (do not attach the prod volume instance to lab).
- Do **not** restart production so a lab pack appears in the team Gallery.
- Do **not** `railway up` production unless Jeff asked to **promote**.
- Do **not** write lab `job.json` into live `tenants/ws_*`.
- Connect Drive / Google login on lab only after the lab callback URLs are on the Google OAuth client:

  - `https://varyforge-studio-lab.up.railway.app/api/drive/oauth/callback`
  - `https://varyforge-studio-lab.up.railway.app/api/auth/google/callback`

  Password login works without those. Until they are added, do not click
  Connect Google on lab — the client still belongs to the live redirect list.

## Isolation that is already true

- Railway env, public hostname, and volume **instance** are separate.
- Generate on lab hits lab Fast. Generate on live hits live Fast.
- `VARIANT_LAB=1` paints the amber “LAB — experiments only” banner. Live does
  not set that flag, so the banner stays off even if this code is promoted.
- R2 keys are `inputs/{source_id}/` with a random 12-hex id, so the shared
  mailbox does not collide with live packs.

## Promote

When a lab recipe looks right: pin that Fast digest on **live** Fast only,
then tell the team. Studio production stays on the last promoted deploy.
