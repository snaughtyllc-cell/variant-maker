from variant_maker.server.drive_names import unique_upload_name


def test_no_collision_keeps_name():
    assert unique_upload_name("v01.mp4", set()) == "v01.mp4"


def test_collision_suffixes():
    existing = {"v01.mp4"}
    assert unique_upload_name("v01.mp4", existing) == "v01 (1).mp4"
    existing.add("v01 (1).mp4")
    assert unique_upload_name("v01.mp4", existing) == "v01 (2).mp4"


def test_collision_without_extension():
    assert unique_upload_name("readme", {"readme"}) == "readme (1)"
