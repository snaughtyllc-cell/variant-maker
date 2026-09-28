#!/usr/bin/env bash
# Seed snaughtyllc-cell/varimo-live from the current Live Studio snapshot.
# Does NOT merge Lab (tier1). Create the empty GitHub repo first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LIVE_REMOTE="${LIVE_REMOTE:-https://github.com/snaughtyllc-cell/varimo-live.git}"
SEED_REF="${SEED_REF:-origin/cursor/railway-runpod-split-c975}"

if ! grep -q '"lane": "lab"' varimo-lane.json; then
  echo "Seed from the Lab GitHub (variant-maker), not from Live." >&2
  exit 1
fi

if ! git ls-remote "$LIVE_REMOTE" HEAD >/dev/null 2>&1; then
  echo "Create empty GitHub repo snaughtyllc-cell/varimo-live (no README), then:" >&2
  echo "  https://github.com/new" >&2
  echo "Install the Cursor GitHub App on that repo, then rerun:" >&2
  echo "  LIVE_REMOTE=$LIVE_REMOTE $0" >&2
  exit 1
fi

git fetch origin cursor/railway-runpod-split-c975
git push "$LIVE_REMOTE" "${SEED_REF}:refs/heads/main"

work="$(mktemp -d)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
git clone --depth 1 --branch main "$LIVE_REMOTE" "$work"
mkdir -p "$work/docs/ops"
cp "$ROOT/deploy/varimo-lane.live.json" "$work/varimo-lane.json"
cp "$ROOT/docs/ops/two-githubs.md" "$work/docs/ops/two-githubs.md"
git -C "$work" add varimo-lane.json docs/ops/two-githubs.md
if git -C "$work" diff --cached --quiet; then
  echo "Live repo already has the lane file."
  exit 0
fi
git -C "$work" -c user.email="varimo-bot@local" -c user.name="varimo" \
  commit -m "chore: this GitHub is Live (copy from Lab, never merge)"
git -C "$work" push origin HEAD:main
echo "Seeded snaughtyllc-cell/varimo-live from $SEED_REF. Point Railway at that repo."
