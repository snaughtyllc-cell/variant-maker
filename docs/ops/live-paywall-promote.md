# Promote Agency paywall to Live

Lab `#108` is merged to `tier1`. Do **not** `git merge` Lab into Live.

The Live-adapted patch is `dist/varimo-live-agency-paywall.patch` (this
repo). Apply it on `snaughtyllc-cell/varimo-live` / `main`:

```bash
git clone https://github.com/snaughtyllc-cell/varimo-live.git
cd varimo-live
git checkout -b cursor/paywall-auto-enroll-b385
git apply --check ../variant-maker/dist/varimo-live-agency-paywall.patch
git apply ../variant-maker/dist/varimo-live-agency-paywall.patch
# commit, PR, merge to main
```

Live already had a pack-quota ladder (Creator / Studio / Agency 100-pack
hard stop). This patch:

- Adds `/pricing` + Stripe Checkout + webhook auto-invite
- Makes **Agency $200 / uncapped** so paid seats are not hard-stopped
- Paid first login creates `plan=agency` (not Creator)
- Typical Fast 20-pack copy: ~10 minutes → 540 packs / 10,800 copies

Jeff-invited `internal` testers stay uncapped. Creator / Studio admin
plans are unchanged.

Checkout stays “not connected” until Railway Live has
`STRIPE_RESTRICTED_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_AGENCY`.
Webhook: `https://<live-studio>/api/billing/webhook`.

`varimo.io/pricing` must point at Live Studio `/pricing` (custom domain
or redirect). This repo cannot push to `varimo-live` (403).
