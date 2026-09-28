from variant_maker.farm.layout import source_output_subfolder


def test_source_output_subfolder_is_stem_plus_sha8():
    assert source_output_subfolder("clip.mp4", "abcdef123456") == "clip__abcdef12"
    assert source_output_subfolder("/tmp/a/Vacation.MOV", "deadbeef") == "Vacation__deadbeef"


def test_source_output_subfolder_falls_back_when_name_or_sha_empty():
    assert source_output_subfolder("", "abc") == "source__abc"
    assert source_output_subfolder("clip.mp4", "") == "clip__unknown"
