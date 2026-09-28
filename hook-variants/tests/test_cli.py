from __future__ import annotations

from hook_variants.cli import main


def test_help_lists_subcommands(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "place" in out
    assert "handoff" in out
    assert "--text" in out


def test_missing_video_is_error(capsys) -> None:
    code = main(["/tmp/does-not-exist-hook-variants.mp4", "--text", "hi"])
    assert code == 1
    err = capsys.readouterr().err
    assert "not found" in err
