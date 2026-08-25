# Launch — first testers

Working brief (pricing, plans, uniqueness loop, DIFM):
`docs/superpowers/specs/2026-08-25-launch-and-unit-economics.md`

Live Studio: https://varyforge-studio-production.up.railway.app

## This week

1. Invite-only. Jeff mints a **new workspace** invite (Admin). That workspace
   lands on **Creator**: Studio / Gallery / Drops / Drive, **200 Fast copies /
   30 days**, no Team / Workflows / HQ.
2. First reel: Fast **8**, not 20. Phone Gallery Share without ZIP. They post.
   They label Drops (unlabeled = pass).
3. Then Fast 20. Batch sources in **one** Generate (idle 10 min is billed once).
4. Do **not** wait for Stripe. Cap is in `tenants.json` (`plan` + usage).
   Admin can PATCH the plan (Creator / Pro / Agency / Internal).

Jeff's own studio stays **internal** (uncapped, all tabs) until he sets a plan.

## Do not

- Raise uniqueness gate / `TARGET_BITS`.
- Put `VF_LAB` on live Fast.
- Public signup.
- Dump 20 copies the same day (strategy, even DIY).
