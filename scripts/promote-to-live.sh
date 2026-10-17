#!/usr/bin/env bash
# Copy listed files into dist/promote-to-live.tgz for the Live GitHub.
# Does NOT git merge. Unpack on snaughtyllc-cell/varimo-live and commit there.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f varimo-lane.json ]]; then
  echo "varimo-lane.json missing — run this from the Lab repo root." >&2
  exit 1
fi
if ! grep -q '"lane": "lab"' varimo-lane.json; then
  echo "This checkout is not Lab. Promote copies Lab → Live, not the other way." >&2
  exit 1
fi
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path> [path ...]" >&2
  echo "Example: $0 web/app/page.tsx web/app/globals.css" >&2
  echo "Then unpack dist/promote-to-live.tgz on varimo-live and commit. Do not git merge." >&2
  exit 1
fi

out_dir="$ROOT/dist"
mkdir -p "$out_dir"
tarball="$out_dir/promote-to-live.tgz"
# Reject git-merge as a "path" so a confused operator gets a hard no.
for arg in "$@"; do
  if [[ "$arg" == *"git merge"* ]] || [[ "$arg" == "merge" ]]; then
    echo "Do not git merge Lab into Live. Pass file paths to copy." >&2
    exit 1
  fi
done

tar -czf "$tarball" "$@"
echo "Wrote $tarball"
echo "Unpack on snaughtyllc-cell/varimo-live, review, commit. Do not git merge."
