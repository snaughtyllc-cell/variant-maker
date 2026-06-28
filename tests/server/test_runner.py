from variant_maker.server.events import VariantEvent, event_to_dict


def test_variant_event_to_dict_roundtrips_fields():
    e = VariantEvent(
        source_id="s1", index=3, state="done",
        attempt=2, max_attempts=3, status="ok",
        quality={"vmaf": 91.0}, filename="clip_v03_abcd1234.mp4",
    )
    d = event_to_dict(e)
    assert d == {
        "source_id": "s1", "index": 3, "state": "done",
        "attempt": 2, "max_attempts": 3, "status": "ok",
        "quality": {"vmaf": 91.0}, "filename": "clip_v03_abcd1234.mp4",
    }


def test_variant_event_defaults():
    e = VariantEvent(source_id="s1", index=1, state="rendering")
    d = event_to_dict(e)
    assert d["attempt"] == 0 and d["status"] is None and d["quality"] is None
