#!/usr/bin/env bash
# Apply the Lab → Live file patch onto a varimo-live checkout.
# Does NOT git merge. Run this from snaughtyllc-cell/varimo-live, not Lab.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f varimo-lane.json ]]; then
  echo "Run this from a variant-maker / varimo-live checkout." >&2
  exit 1
fi
if ! grep -q '"lane": "live"' varimo-lane.json; then
  echo "This checkout is not Live. Apply the patch on snaughtyllc-cell/varimo-live." >&2
  echo "Do not git merge Lab into Live." >&2
  exit 1
fi

patch="${1:-}"
if [[ -z "$patch" ]]; then
  echo "Usage: $0 /path/to/promote-21691c4-to-live.patch" >&2
  echo "Download: docs/ops/patches/promote-21691c4-to-live.patch from Lab." >&2
  exit 1
fi
if [[ ! -f "$patch" ]]; then
  echo "Patch not found: $patch" >&2
  exit 1
fi

git am "$patch"
echo "Applied $patch. Review, push the branch, open a PR to Live main."
echo "Do not git merge Lab history."
