# Sentry + PostHog (optional)

Studio records finished jobs locally in `{workspace}/usage.jsonl` either way.
These env vars only add remote breadcrumbs. Empty = no-op. Missing packages
do not fail a render.

| Variable | Where | What |
|---|---|---|
| `SENTRY_DSN` | Railway Studio (lab first) | Optional `sentry_sdk` — add the extra only if you want it |
| `POSTHOG_KEY` or `POSTHOG_API_KEY` | Railway Studio | Server `/capture/` via urllib (no npm) |
| `POSTHOG_HOST` | Railway Studio | Default `https://us.i.posthog.com` |

Event: `job_completed` with `job_id`, `prep_mode`, `quality_mode`,
`fast_copies`, `hq_preps`. `distinct_id` is the signed-in operator email
when Studio auth is on, else the workspace id.

Each finished job also stores `customer_email` on the `usage.jsonl` row.
Admin and Team show Fast / HQ / packs **per member** for the last 7 days.

Do not put keys on the Fast worker image. Lab Studio first; live after Jeff
signs the week readout.
