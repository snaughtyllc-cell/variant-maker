"""Match Reels to Gallery copies; pack totals skip unlinked (unknown ≠ 0)."""
from __future__ import annotations

from tests.server.fakes import FakeRunner
from variant_maker.server.instagram_insights import (
    IgMedia,
    VariantLink,
    gallery_analytics,
    match_media,
    normalize_caption,
    pack_analytics,
    parse_insights_payload,
    permalink_key,
)
from variant_maker.server.jobs import JobStore
from variant_maker.server.workspace import Workspace


def test_permalink_key_strips_query_and_host():
    assert permalink_key("https://www.instagram.com/reel/AbC123/?igsh=xyz") == "abc123"
    assert permalink_key("instagram.com/p/AbC123/") == "abc123"


def test_normalize_caption_flattens_drive_newlines():
    assert normalize_caption("POV: boil\n\n#reels") == "pov: boil #reels"


def test_match_prefers_permalink_then_unique_caption():
    variants = [
        VariantLink("s1", 1, post_url="https://instagram.com/reel/Aaa/", caption="hook one #x"),
        VariantLink("s1", 2, post_url=None, caption="hook two #y"),
        VariantLink("s1", 3, post_url=None, caption="hook two #y"),
    ]
    media = [
        IgMedia("m1", permalink="https://www.instagram.com/reel/Aaa/", caption="ignored"),
        IgMedia("m2", permalink="https://www.instagram.com/reel/Bbb/", caption="hook two #y"),
        IgMedia("m3", permalink="https://www.instagram.com/reel/Ccc/", caption="hook two #y"),
    ]
    matches = {(m.index, m.via, m.media_id) for m in match_media(variants, media)}
    assert (1, "permalink", "m1") in matches
    # Duplicate caption on two copies AND two Reels — do not guess.
    assert not any(idx in (2, 3) for idx, _via, _mid in matches)


def test_unique_caption_links_when_exactly_one_each():
    variants = [
        VariantLink("s1", 7, post_url=None, caption="  Unique Hook  "),
    ]
    media = [
        IgMedia("media7", permalink="https://instagram.com/reel/Zzz/", caption="unique hook"),
    ]
    hits = match_media(variants, media)
    assert len(hits) == 1
    assert hits[0].via == "caption"
    assert hits[0].media_id == "media7"


def test_pack_analytics_unknown_is_not_zero():
    class V:
        def __init__(self, media=None, views=None):
            self.ig_media_id = media
            self.ig_insights = {"views": views} if views is not None else None

    empty = pack_analytics([V(), V()])
    assert empty["insights_views"] is None
    assert empty["insights_linked"] == 0
    assert empty["insights_unknown"] == 2

    mixed = pack_analytics([V("m1", 100), V()])
    assert mixed["insights_views"] == 100
    assert mixed["insights_linked"] == 1
    assert mixed["insights_unknown"] == 1


def test_gallery_analytics_ranks_the_winning_source():
    class V:
        def __init__(self, media, views):
            self.ig_media_id = media
            self.ig_insights = {"views": views}

    class S:
        def __init__(self, source_id, filename, variants):
            self.source_id = source_id
            self.filename = filename
            self.variants = variants

    body = gallery_analytics([
        S("quiet", "quiet.mp4", [V("a", 10)]),
        S("winner", "winner.mp4", [V("b", 900), V("c", 100)]),
    ])
    assert body["insights_views"] == 1010
    assert body["ranked"][0]["source_id"] == "winner"
    assert body["ranked"][0]["insights_views"] == 1000


def test_parse_insights_reads_total_value_and_values():
    body = {
        "data": [
            {"name": "views", "total_value": {"value": 312400}},
            {"name": "likes", "values": [{"value": 12}]},
        ]
    }
    assert parse_insights_payload(body) == {"views": 312400, "likes": 12}


def test_set_ig_insights_survives_hydrate(tmp_path):
    store = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    job = store.create_job([("a.mp4", b"x")], count=1)
    store.wait(job.job_id, timeout=5)
    src = store.get(job.job_id).sources[0]
    idx = src.variants[0].index
    updated = store.set_ig_insights(
        src.source_id, idx,
        ig_media_id="m9",
        ig_user_id="17841",
        insights={"views": 44, "likes": 2, "fetched_at": "2026-09-02T00:00:00Z"},
        post_url="https://www.instagram.com/reel/HydrateIg/",
    )
    assert updated is not None
    assert updated.ig_media_id == "m9"
    assert updated.ig_insights["views"] == 44

    store2 = JobStore(Workspace(str(tmp_path)), FakeRunner({}))
    assert store2.hydrate_from_disk() == 1
    restored = store2.get(job.job_id).sources[0].variants[0]
    assert restored.ig_media_id == "m9"
    assert restored.ig_user_id == "17841"
    assert restored.ig_insights["views"] == 44
    assert restored.post_url == "https://www.instagram.com/reel/HydrateIg/"
