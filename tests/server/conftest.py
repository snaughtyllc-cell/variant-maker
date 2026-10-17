"""Server tests seed jobs with old created_utc stamps (Jan / Jul fixtures).

Production default is 7-day age prune. That would empty Gallery in those tests
on list()/hydrate. Opt in with JobStore(..., gallery_keep_hours=24) or by
deleting VARIANT_GALLERY_KEEP_HOURS.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_gallery_age_prune_unless_opted_in(monkeypatch):
    monkeypatch.setenv("VARIANT_GALLERY_KEEP_HOURS", "0")
