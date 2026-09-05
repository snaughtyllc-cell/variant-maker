from variant_maker.hunt_timing import (
    add_encode,
    add_peer,
    add_quality,
    add_uniqueness,
    classify_signature,
    mark_reject,
    new_accumulator,
    slot_from_acc,
    summarize_pack,
    worker_id,
)


def test_slot_counts_rejected_encodes_not_only_the_shipped_file():
    acc = new_accumulator()
    add_encode(acc, 10.0)
    add_uniqueness(acc, 4.0)
    mark_reject(acc, "source_ssim")
    add_encode(acc, 11.0)
    add_uniqueness(acc, 3.0)
    add_quality(acc, 1.0)
    slot = slot_from_acc(acc, index=3, status="ok", elapsed_s=28.0)
    assert slot["candidates"] == 2
    assert slot["accepted_on_candidate"] == 2
    assert slot["rejected_encode_s"] == 10.0
    assert slot["reject_reasons"] == ["source_ssim"]
    assert slot["uniqueness_s"] == 7.0


def test_summarize_pack_does_not_hide_hunt_behind_successful_encodes():
    slots = []
    for i in range(1, 4):
        acc = new_accumulator()
        add_encode(acc, 5.0)
        if i == 3:
            mark_reject(acc, "peer_ssim")
            add_encode(acc, 6.0)
        add_uniqueness(acc, 2.0)
        add_peer(acc, 0.5)
        slots.append(slot_from_acc(acc, index=i, status="ok", elapsed_s=10.0 * i))
    pack = summarize_pack(slots, wall_s=30.0, jobs=8, worker_id="pod-1")
    assert pack["candidates"] == 4
    assert pack["accepted"] == 3
    assert pack["rejected_candidates"] == 1
    assert pack["attempts_per_accepted"] == round(4 / 3, 3)
    assert pack["time_to_first_s"] == 10.0
    assert pack["by_slot"][-1]["candidates"] == 2
    assert pack["jobs"] == 8
    assert pack["worker_id"] == "pod-1"


def test_classify_cold_start_when_startup_dominates_wall():
    sig = classify_signature({
        "wall_s": 80.0, "startup_s": 45.0, "upload_s": 2.0,
        "encode_s": 20.0, "uniqueness_s": 5.0, "peer_s": 1.0,
        "rejected_encode_s": 2.0, "attempts_per_accepted": 1.1,
    })
    assert sig == "cold_start_bound"


def test_classify_hunt_when_rejected_encodes_and_retries_dominate():
    sig = classify_signature({
        "wall_s": 200.0, "startup_s": 8.0, "upload_s": 5.0,
        "encode_s": 120.0, "uniqueness_s": 40.0, "peer_s": 10.0,
        "rejected_encode_s": 80.0, "attempts_per_accepted": 2.1,
    })
    assert sig == "hunt_bound"


def test_classify_encode_when_few_rejects():
    sig = classify_signature({
        "wall_s": 120.0, "startup_s": 5.0, "upload_s": 4.0,
        "encode_s": 90.0, "uniqueness_s": 8.0, "peer_s": 2.0,
        "rejected_encode_s": 5.0, "attempts_per_accepted": 1.05,
    })
    assert sig == "encode_bound"


def test_classify_upload_when_delivery_dominates():
    sig = classify_signature({
        "wall_s": 100.0, "startup_s": 5.0, "upload_s": 50.0,
        "encode_s": 20.0, "uniqueness_s": 5.0, "peer_s": 1.0,
        "rejected_encode_s": 0.0, "attempts_per_accepted": 1.0,
    })
    assert sig == "queue_or_upload_bound"


def test_worker_id_prefers_runpod_pod():
    assert worker_id({"RUNPOD_POD_ID": "abc", "HOSTNAME": "box"}) == "abc"
    assert worker_id({"HOSTNAME": "box"}) == "box"
    assert worker_id({}) is None
