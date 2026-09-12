"""Pin Lab Fast on Lab Studio boot. Never Live Fast."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

LAB_FAST_ENDPOINT = "xar25v77v3j27u"
LIVE_FAST_ENDPOINT = "j0b1q4iuunzhnq"
DEFAULT_IMAGE = "ghcr.io/snaughtyllc-cell/variant-fast:lab"
_PATCH_URL = "https://api.runpod.io/v2/serverless/{endpoint}"


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes"}


def target_endpoint(environ: Mapping[str, str] | None = None) -> str | None:
    """Lab Fast id only. Live id is never returned."""
    env = environ if environ is not None else os.environ
    if not _truthy(env.get("VARIANT_LAB")):
        return None
    lab = (env.get("RUNPOD_FAST_LAB_ENDPOINT_ID") or "").strip()
    fast = (env.get("RUNPOD_FAST_ENDPOINT_ID") or "").strip()
    if lab == LAB_FAST_ENDPOINT or fast == LAB_FAST_ENDPOINT:
        return LAB_FAST_ENDPOINT
    return None


def _default_patch(url: str, api_key: str, image: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps({"image": image}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def pin_lab_fast_endpoint(
    environ: Mapping[str, str] | None = None,
    patch: Callable[[str, str, str], tuple[int, str]] | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    endpoint = target_endpoint(env)
    if endpoint is None:
        if not _truthy(env.get("VARIANT_LAB")):
            return "skipped_not_lab"
        return "skipped_not_lab_endpoint"
    if endpoint == LIVE_FAST_ENDPOINT:
        return "skipped_not_lab_endpoint"
    key = (env.get("RUNPOD_API_KEY") or "").strip()
    if not key:
        return "skipped_no_key"
    image = (env.get("VARIANT_LAB_FAST_IMAGE") or DEFAULT_IMAGE).strip() or DEFAULT_IMAGE
    url = _PATCH_URL.format(endpoint=endpoint)
    if LIVE_FAST_ENDPOINT in url:
        return "skipped_not_lab_endpoint"
    do_patch = patch or _default_patch
    status, body = do_patch(url, key, image)
    if status >= 300:
        print(f"lab fast pin HTTP {status}: {body[:200]}", flush=True)
        return f"error_{status}"
    print(f"Pinned lab {endpoint} to {image}. Did not PATCH live.", flush=True)
    return "pinned"
