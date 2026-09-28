"""Agency overage math + paid-grant invite (no Stripe SDK)."""
from __future__ import annotations

from variant_maker.server.billing import (
    AGENCY_INCLUDED_FAST_HOURS,
    AGENCY_OVERAGE_USD_PER_HOUR,
    apply_stripe_event,
    fast_hour_meter,
    get_plan,
    grant_paid_subscription,
    overage_snapshot,
    typical_fast20_throughput,
)
from variant_maker.server.job_metrics import FAST_USD_PER_HOUR
from variant_maker.server.tenants import TenantStore, provision_login


def test_agency_includes_ninety_fast_hours_by_default():
    """Product lock: $200 Agency includes 90 Fast hours, not the first-cut 40."""
    assert AGENCY_INCLUDED_FAST_HOURS == 90
    plan = get_plan("agency", environ={})
    assert plan.included_fast_hours == 90
    packs, copies = typical_fast20_throughput(90)
    assert packs == 540
    assert copies == 10800


def test_agency_overage_is_worker_hours_not_per_pack():
    plan = get_plan("agency")
    assert plan.price_usd == 200
    assert plan.included_fast_hours == AGENCY_INCLUDED_FAST_HOURS
    assert plan.overage_usd_per_hour == AGENCY_OVERAGE_USD_PER_HOUR
    assert plan.cogs_fast_usd_per_hour == FAST_USD_PER_HOUR
    assert plan.overage_usd_per_hour > plan.cogs_fast_usd_per_hour
    included = overage_snapshot(plan, AGENCY_INCLUDED_FAST_HOURS * 3600)
    assert included.overage_fast_seconds == 0
    assert included.overage_usd == 0
    assert included.remaining_fast_seconds == 0
    hour_over = overage_snapshot(plan, (AGENCY_INCLUDED_FAST_HOURS + 1) * 3600)
    assert hour_over.overage_fast_seconds == 3600
    assert hour_over.overage_usd == AGENCY_OVERAGE_USD_PER_HOUR


def test_agency_hours_and_rate_are_env_overridable(monkeypatch):
    plan = get_plan("agency", environ={
        "VARIANT_PLAN_AGENCY_FAST_HOURS": "10",
        "VARIANT_PLAN_AGENCY_OVERAGE_USD": "0.80",
    })
    assert plan.included_fast_hours == 10
    assert plan.overage_usd_per_hour == 0.80
    snap = overage_snapshot(plan, 11 * 3600)
    assert snap.overage_usd == 0.80


def test_billing_meter_drains_while_a_fast_job_is_running(tmp_path):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from variant_maker.server.billing import billing_status_payload
    from variant_maker.server.jobs import Job, JobSource, VariantInfo
    from variant_maker.server.tenants import BillingRecord
    from variant_maker.server.usage import record_job
    from variant_maker.server.workspace import Workspace

    now = datetime(2026, 9, 10, 14, 0, tzinfo=UTC)
    rec = BillingRecord(
        email="ops@x.com",
        plan="agency",
        status="active",
        period_start_utc="2026-09-01T00:00:00Z",
        period_end_utc="2026-10-01T00:00:00Z",
    )
    ws = Workspace(str(tmp_path))
    variants = [
        VariantInfo(source_id="s1", index=1, filename="v01.mp4", status="ok", quality={"vmaf": 95.0}),
    ]
    finished = Job(
        job_id="done1",
        count=1,
        created_utc="2026-09-10T12:00:00Z",
        sources=[JobSource(source_id="s1", filename="a.mp4", requested=1, variants=variants)],
        state="done",
        quality_mode="fast",
    )
    finished.telemetry = {"billed": {"real_work_s": 3600}}
    record_job(ws, finished, now=now - timedelta(hours=1))
    running = SimpleNamespace(
        quality_mode="fast",
        state="running",
        created_utc=(now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        telemetry={},
    )
    payload = billing_status_payload(
        rec=rec, workspace=ws, is_admin=False, jobs=[running], now=now,
    )
    assert payload["fast_seconds"] == 3600 + 1800
    assert payload["usage"]["uncapped"] is False
    assert payload["usage"]["tone"] == "included"
    assert payload["usage"]["meter_line"] == "88.5 of 90h left"
    assert payload["usage"]["hard_stop"] is False


def test_fast_hour_meter_drains_to_zero_then_usage():
    plan = get_plan("agency", environ={})
    full = fast_hour_meter(plan, overage_snapshot(plan, 0))
    assert full["uncapped"] is False
    assert full["hard_stop"] is False
    assert full["tone"] == "included"
    assert full["remaining_pct"] == 100
    assert full["meter_line"] == "90 of 90h left"
    half = fast_hour_meter(plan, overage_snapshot(plan, 45 * 3600))
    assert half["remaining_pct"] == 50
    assert half["meter_line"] == "45 of 90h left"
    floor = fast_hour_meter(plan, overage_snapshot(plan, 90 * 3600))
    assert floor["remaining_pct"] == 0
    assert floor["tone"] == "included"
    assert floor["meter_line"] == "0 of 90h left"
    over = fast_hour_meter(plan, overage_snapshot(plan, 91 * 3600))
    assert over["tone"] == "usage"
    assert over["remaining_pct"] == 0
    assert over["meter_line"] == "Usage"
    assert over["hard_stop"] is False


def test_under_included_fast_hours_has_no_overage():
    snap = overage_snapshot(get_plan("agency"), 1000)
    assert snap.overage_usd == 0
    assert snap.remaining_fast_seconds == AGENCY_INCLUDED_FAST_HOURS * 3600 - 1000


def test_paid_grant_invites_unknown_email(tmp_path):
    store = TenantStore(str(tmp_path / "tenants.json"))
    assert grant_paid_subscription(store, email="ops@X.com", plan="agency") == "invited"
    inv = store.list_invites()
    assert len(inv) == 1
    assert inv[0].email == "ops@x.com"
    assert inv[0].kind == "new_workspace"
    bill = store.get_billing("ops@x.com")
    assert bill is not None
    assert bill.plan == "agency"
    assert bill.status == "active"
    assert bill.workspace_id is None


def test_paid_grant_is_idempotent_and_does_not_duplicate_invite(tmp_path):
    store = TenantStore(str(tmp_path / "tenants.json"))
    grant_paid_subscription(
        store, email="ops@x.com", stripe_checkout_session_id="cs_1",
    )
    grant_paid_subscription(
        store, email="ops@x.com", stripe_checkout_session_id="cs_1",
        stripe_subscription_id="sub_1",
    )
    assert len(store.list_invites()) == 1
    bill = store.get_billing("ops@x.com")
    assert bill is not None
    assert bill.stripe_subscription_id == "sub_1"


def test_first_sign_in_after_payment_creates_workspace_and_binds_billing(tmp_path):
    store = TenantStore(str(tmp_path / "t.json"))
    grant_paid_subscription(store, email="ops@x.com")
    user = provision_login(
        store, email="ops@x.com", name="Ops", admin_email="jeff@x.com",
    )
    assert user is not None and user.role == "owner"
    bill = store.get_billing("ops@x.com")
    assert bill is not None
    assert bill.workspace_id == user.workspace_id
    assert store.get_billing_for_workspace(user.workspace_id) is not None


def test_checkout_completed_webhook_invites(tmp_path):
    store = TenantStore(str(tmp_path / "t.json"))
    action = apply_stripe_event(store, {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "payment_status": "paid",
                "customer": "cus_1",
                "subscription": "sub_1",
                "customer_details": {"email": "buyer@x.com"},
                "metadata": {"plan": "agency"},
            }
        },
    })
    assert action == "invited"
    assert store.get_billing("buyer@x.com").stripe_customer_id == "cus_1"


def test_unpaid_checkout_does_not_invite(tmp_path):
    store = TenantStore(str(tmp_path / "t.json"))
    action = apply_stripe_event(store, {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_unpaid",
                "payment_status": "unpaid",
                "customer_email": "nope@x.com",
            }
        },
    })
    assert action == "unpaid"
    assert store.list_invites() == []
    assert store.get_billing("nope@x.com") is None


def test_subscription_canceled_does_not_drop_the_login(tmp_path):
    store = TenantStore(str(tmp_path / "t.json"))
    grant_paid_subscription(
        store, email="ops@x.com", stripe_subscription_id="sub_1",
    )
    provision_login(store, email="ops@x.com", name="Ops", admin_email="jeff@x.com")
    action = apply_stripe_event(store, {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_1", "status": "canceled", "customer": "cus_1"}},
    })
    assert action == "canceled"
    assert store.get_user("ops@x.com") is not None
    assert store.get_billing("ops@x.com").status == "canceled"
