# Codex / Live agent — ship Agency paywall + Fast-hour meter

Paste this into a Cursor agent **opened on `snaughtyllc-cell/varimo-live`**, not Lab.
Do **not** `git merge` Lab into Live.

```
You are on snaughtyllc-cell/varimo-live. Default branch is main.

1. Fetch the two-commit patch from Lab (do not merge Lab history):

   curl -fsSL -o /tmp/varimo-live-agency-paywall.patch \
     https://raw.githubusercontent.com/snaughtyllc-cell/variant-maker/cursor/agency-fast-meter-b385/dist/varimo-live-agency-paywall.patch

   git checkout main
   git pull origin main
   git checkout -b cursor/paywall-auto-enroll-b385
   git am /tmp/varimo-live-agency-paywall.patch

   If git am says those commits are already applied, use only the meter commit:

   curl -fsSL -o /tmp/varimo-live-agency-fast-meter.patch \
     https://raw.githubusercontent.com/snaughtyllc-cell/variant-maker/cursor/agency-fast-meter-b385/dist/varimo-live-agency-fast-meter.patch
   git am /tmp/varimo-live-agency-fast-meter.patch

2. Product lock (do not drift):
   - One paid plan: Agency $200/month
   - 90 Fast hours / 30 days, then $0.75/hr overage recorded (not invoiced yet)
   - Meter drains 90 → 0, then amber "Usage" tag. NOT "uncapped". NOT unlimited.
   - Generate does not hard-stop after 90 hours
   - Jeff-invited internal testers stay uncapped (no Stripe record = no bar)
   - Creator/Studio pack hard-stops stay as they are
   - Do not put Fast COGS ($0.58/hr) on /pricing or marketing
   - Checkout must omit payment_method_types and automatic_tax

3. Commit if needed, push, open a PR to main, merge it.

4. Stripe (Dashboard, live mode when testers pay real money):
   - Product: Agency
   - Price: $200 USD / month recurring. Copy the price id (price_…)
   - Developers → Webhooks → add
     https://<live-studio-host>/api/billing/webhook
     events: checkout.session.completed, checkout.session.async_payment_succeeded,
     customer.subscription.updated, customer.subscription.deleted
   - Copy the webhook signing secret (whsec_…)
   - Prefer a restricted key (rk_) over sk_

5. Railway Live Studio service env:
   STRIPE_RESTRICTED_KEY=rk_…
   STRIPE_WEBHOOK_SECRET=whsec_…
   STRIPE_PRICE_AGENCY=price_…
   If VARIANT_PLAN_AGENCY_FAST_HOURS=40 exists, set 90 or delete it.
   Redeploy.

6. Point https://varimo.io/pricing at Live Studio /pricing
   (custom domain or redirect). Lab Railway is the wrong host.

7. Landing page copy update only (existing Design page, no redesign):

   Agency — $200/month
   90 Fast hours / 30 days, then $0.75/hr. Generate keeps running.
   Not unlimited. A typical talking-head Fast 20-pack is about 10 minutes
   (~540 packs / ~10,800 copies in the included block). Typical, not a promise.
   Analytics coming soon.
   CTA: https://varimo.io/pricing
```
