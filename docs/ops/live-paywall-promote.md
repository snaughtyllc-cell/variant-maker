# Promote Agency paywall to Live

Lab `#108` is merged to `tier1`. Do **not** `git merge` Lab into Live.

The Live-adapted patch is `dist/varimo-live-agency-paywall.patch` (this
repo; two commits). Apply it on `snaughtyllc-cell/varimo-live` / `main`.
If the first Agency paywall commit is already on Live, apply only
`dist/varimo-live-agency-fast-meter.patch`.

```bash
git clone https://github.com/snaughtyllc-cell/varimo-live.git
cd varimo-live
git checkout -b cursor/paywall-auto-enroll-b385
git am ../variant-maker/dist/varimo-live-agency-paywall.patch
# or, if checkout + webhook already landed:
# git am ../variant-maker/dist/varimo-live-agency-fast-meter.patch
# commit, PR, merge to main
```

Live already had a pack-quota ladder (Creator / Studio / Agency 100-pack
hard stop). This patch:

- Adds `/pricing` + Stripe Checkout + webhook auto-invite
- Makes **Agency $200 / 90 Fast hours**. The sidebar meter drains to 0,
  then flips to an amber **Usage** tag. Generate does **not** hard-stop.
  Do not label Agency “uncapped.”
- Paid first login creates `plan=agency` (not Creator)
- Typical Fast 20-pack copy: ~10 minutes → 540 packs / 10,800 copies

Jeff-invited `internal` testers stay uncapped. Creator / Studio admin
plans keep their pack meters and hard stops.

Checkout stays “not connected” until Railway Live has
`STRIPE_RESTRICTED_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_AGENCY`.
Webhook: `https://<live-studio>/api/billing/webhook`.

`varimo.io/pricing` must point at Live Studio `/pricing` (custom domain
or redirect). This repo cannot push to `varimo-live` (403).
