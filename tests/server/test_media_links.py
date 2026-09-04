from variant_maker.server.media_links import (
    DRIVE_OUTPUT_KEEP_HOURS,
    OUTPUT_KEEP_HOURS,
    input_key,
    output_key,
    outputs_expire_utc,
    package_zip_key,
    upload_key,
)


def test_object_keys_are_scoped_and_basename_only():
    assert input_key("s1", "../../etc/passwd") == "inputs/s1/passwd"
    assert output_key("s1", "v01.mp4") == "outputs/s1/v01.mp4"
    assert upload_key("up1", "clip.mp4") == "uploads/up1/clip.mp4"
    assert package_zip_key("s1") == "outputs/s1/variants.zip"


def test_download_outputs_expire_inside_72h_window():
    exp = outputs_expire_utc(
        now=__import__("datetime").datetime(2026, 9, 4, 12, tzinfo=__import__("datetime").UTC),
        destination="download",
    )
    assert exp == "2026-09-06T12:00:00Z"  # +48h default
    assert 24 <= OUTPUT_KEEP_HOURS <= 72


def test_drive_delivered_outputs_expire_quickly():
    exp = outputs_expire_utc(
        now=__import__("datetime").datetime(2026, 9, 4, 12, tzinfo=__import__("datetime").UTC),
        destination="google_drive",
    )
    assert exp == "2026-09-04T13:00:00Z"
    assert DRIVE_OUTPUT_KEEP_HOURS <= 2
