import pytest

from variant_maker.sampler import derive_seed, sample
from variant_maker.presets import MEDIUM


def test_derive_seed_is_deterministic():
    assert derive_seed(42, 1) == derive_seed(42, 1)
    assert derive_seed(42, 1) != derive_seed(42, 2)


@pytest.mark.xfail(reason="Phase 3: sample() not implemented", strict=True)
def test_sample_is_reproducible():
    s = derive_seed(42, 1)
    assert sample(MEDIUM, s) == sample(MEDIUM, s)


@pytest.mark.xfail(reason="Phase 3: audio.speed must equal video.speed", strict=True)
def test_audio_speed_matches_video_speed():
    p = sample(MEDIUM, derive_seed(1, 1))
    assert p["audio"]["speed"] == p["video"]["speed"]
