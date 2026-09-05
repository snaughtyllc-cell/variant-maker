"""This GitHub is Lab. Live is a second repo — never merge the two."""
import json
from pathlib import Path

from variant_maker.lane import (
    LAB_GITHUB_REPO,
    LIVE_GITHUB_REPO,
    load_lane,
    repo_root,
)

ROOT = Path(__file__).resolve().parents[1]


def test_this_checkout_is_the_lab_github():
    lane = load_lane()
    assert lane["lane"] == "lab"
    assert lane["github_repo"] == LAB_GITHUB_REPO
    assert lane["live_github_repo"] == LIVE_GITHUB_REPO
    assert lane["promote"] == "copy"
    assert "git merge" in " ".join(lane["do_not"]).lower()


def test_live_github_is_a_different_repo_not_a_branch():
    assert LIVE_GITHUB_REPO != LAB_GITHUB_REPO
    assert LIVE_GITHUB_REPO.endswith("/varimo-live")
    lane = load_lane()
    assert "railway-runpod-split" not in lane["live_github_repo"]


def test_claude_and_readme_tell_agents_this_is_lab():
    claude = (ROOT / "CLAUDE.md").read_text()
    readme = (ROOT / "README.md").read_text()
    ops = (ROOT / "docs/ops/two-githubs.md").read_text()
    assert "THIS REPO IS LAB" in claude
    assert "varimo-live" in claude
    assert "varimo-live" in readme
    assert "copy" in ops.lower()
    assert "do not merge" in ops.lower()


def test_lab_fast_ci_cannot_push_live_latest():
    lab = (ROOT / ".github/workflows/build-variant-fast-lab.yml").read_text()
    assert "-t ghcr.io/snaughtyllc-cell/variant-fast:lab" in lab
    assert "-t ghcr.io/snaughtyllc-cell/variant-fast:latest" not in lab
    live_wf = ROOT / ".github/workflows/build-variant-fast.yml"
    assert not live_wf.exists(), "Live Fast :latest CI belongs on varimo-live, not Lab"
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        text = path.read_text()
        assert "-t ghcr.io/snaughtyllc-cell/variant-fast:latest" not in text, path.name
        assert "docker push ghcr.io/snaughtyllc-cell/variant-fast:latest" not in text, path.name


def test_live_lane_template_is_live_not_lab():
    raw = json.loads((ROOT / "deploy/varimo-lane.live.json").read_text(encoding="utf-8"))
    assert raw["lane"] == "live"
    assert raw["github_repo"] == LIVE_GITHUB_REPO
    assert raw["lab_github_repo"] == LAB_GITHUB_REPO
    assert raw["promote"] == "copy"


def test_ops_docs_have_no_leftover_conflict_markers():
    markers = ("<<<<<<<", ">>>>>>>")
    for path in (ROOT / "docs").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            assert marker not in text, f"{path.relative_to(ROOT)} has {marker}"


def test_promote_and_seed_scripts_exist():
    promote = ROOT / "scripts/promote-to-live.sh"
    seed = ROOT / "scripts/seed-live-repo.sh"
    assert promote.is_file()
    assert seed.is_file()
    text = promote.read_text() + seed.read_text()
    assert "varimo-live" in text
    assert "git merge" in text
    assert repo_root() == ROOT
