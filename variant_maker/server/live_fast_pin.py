"""Pin Live Fast image from Lab Studio boot. Image only. Never env / VF_LAB."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence

LAB_FAST_ENDPOINT = "xar25v77v3j27u"
LIVE_FAST_ENDPOINT = "j0b1q4iuunzhnq"
PINNED_IMAGE = (
    "ghcr.io/snaughtyllc-cell/variant-fast@"
    "sha256:fc5a81090bac281b33eae122c087b19d6c9f0c090f8a68a2c1a2686723866097"
)
# Spent 2026-09-12: Lab health live_fast_pin=pinned v2_patch=200.
ONE_SHOT_ENABLED = False
_V2_PATCH_URL = "https://api.runpod.io/v2/serverless/{endpoint}"
_V1_ENDPOINT_URL = "https://rest.runpod.io/v1/endpoints/{endpoint}"
_USER_AGENT = "varyforge-live-fast-pin/1"
_IMAGE_RE = re.compile(
    r"^ghcr\.io/snaughtyllc-cell/variant-fast@sha256:[a-f0-9]{64}$"
)
LAST_STATUS = "not_run"
LAST_DETAIL = ""

HttpFn = Callable[..., tuple[int, str]]
PatchFn = Callable[[str, str, str], tuple[int, str]]


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes"}


def _falsey(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"0", "false", "no"}


def pin_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    raw = env.get("VARIANT_LIVE_FAST_PIN")
    if raw is not None and str(raw).strip() != "":
        return _truthy(str(raw))
    return ONE_SHOT_ENABLED


def target_endpoint(environ: Mapping[str, str] | None = None) -> str | None:
    """Live Fast id only, and only from Lab Studio."""
    env = environ if environ is not None else os.environ
    if not _truthy(env.get("VARIANT_LAB")):
        return None
    if not pin_enabled(env):
        return None
    return LIVE_FAST_ENDPOINT


def sanitize_detail(text: str, secrets: Sequence[str] = ()) -> str:
    """Health/log snippet: no Lab id, no API keys."""
    out = text or ""
    out = out.replace(LAB_FAST_ENDPOINT, "[lab]")
    out = re.sub(r"api_key=[^&\s\"']+", "api_key=[redacted]", out, flags=re.IGNORECASE)
    out = re.sub(r"(Bearer )\S+", r"\1[redacted]", out, flags=re.IGNORECASE)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return " ".join(out.split())[:240]


def resolve_live_image(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    raw = (env.get("VARIANT_LIVE_FAST_IMAGE") or "").strip()
    if raw:
        return raw
    return PINNED_IMAGE


def _image_ok(image: str) -> bool:
    if not image or not _IMAGE_RE.match(image):
        return False
    if LAB_FAST_ENDPOINT in image:
        return False
    if "VF_LAB" in image:
        return False
    return ":lab" not in image


def _management_keys(env: Mapping[str, str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for name in ("RUNPOD_ENDPOINT_UPDATE_KEY", "RUNPOD_API_KEY"):
        key = (env.get(name) or "").strip()
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _body_forbidden(body: dict | None) -> str | None:
    if not body:
        return None
    if any(k in body for k in ("env", "envVars", "environment")):
        return "refused_env_body"
    blob = json.dumps(body)
    if "VF_LAB" in blob:
        return "refused_vf_lab"
    if LAB_FAST_ENDPOINT in blob:
        return "refused_lab_id"
    return None


def _default_http(
    method: str,
    url: str,
    api_key: str,
    body: dict | None = None,
    **_kw: object,
) -> tuple[int, str]:
    if LAB_FAST_ENDPOINT in url:
        return 0, "refused_lab_url"
    forbidden = _body_forbidden(body)
    if forbidden:
        return 0, forbidden
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), text
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), text
    except (OSError, urllib.error.URLError) as exc:
        return 0, str(exc)


def _default_patch(url: str, api_key: str, image: str) -> tuple[int, str]:
    return _default_http("PATCH", url, api_key, {"image": image})


def pin_live_fast_endpoint(
    environ: Mapping[str, str] | None = None,
    patch: PatchFn | None = None,
    http: HttpFn | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    secrets: list[str] = []

    def finish(status: str, detail: str = "") -> str:
        global LAST_STATUS, LAST_DETAIL
        LAST_STATUS = status
        LAST_DETAIL = sanitize_detail(detail, secrets)
        return status

    if not _truthy(env.get("VARIANT_LAB")):
        return finish("skipped_not_lab")
    if not pin_enabled(env):
        return finish("skipped_disabled")
    endpoint = target_endpoint(env)
    if endpoint != LIVE_FAST_ENDPOINT:
        return finish("skipped_not_live_endpoint")
    keys = _management_keys(env)
    secrets.extend(keys)
    if not keys:
        return finish("skipped_no_key")
    image = resolve_live_image(env)
    if not _image_ok(image):
        return finish("skipped_bad_image")

    v2_url = _V2_PATCH_URL.format(endpoint=endpoint)
    v1_url = _V1_ENDPOINT_URL.format(endpoint=endpoint)
    if LAB_FAST_ENDPOINT in v2_url or LAB_FAST_ENDPOINT in v1_url:
        return finish("skipped_not_live_endpoint")

    v2_body = {"image": image}
    v1_body = {"imageName": image}
    if _body_forbidden(v2_body) or _body_forbidden(v1_body):
        return finish("skipped_bad_image")

    if patch is not None:
        status, body = patch(v2_url, keys[0], image)
        if status >= 300:
            print(
                f"live fast pin HTTP {status}: {sanitize_detail(body[:200], secrets)}",
                flush=True,
            )
            return finish(f"error_{status}", f"v2_patch={status} {body[:200]}")
        print(
            f"Pinned live {endpoint} to {image}. Image only. No VF_LAB. Did not PATCH lab.",
            flush=True,
        )
        return finish("pinned")

    do_http = http or _default_http
    notes: list[str] = []
    last_status = 0
    last_body = ""

    def attempt(
        label: str,
        method: str,
        url: str,
        api_key: str,
        body: dict | None = None,
    ) -> tuple[int, str]:
        if LAB_FAST_ENDPOINT in url:
            notes.append(f"{label}=refused_lab")
            return 0, "refused_lab_url"
        forbidden = _body_forbidden(body)
        if forbidden:
            notes.append(f"{label}={forbidden}")
            return 0, forbidden
        status, text = do_http(method, url, api_key, body)
        notes.append(f"{label}={status}")
        return status, text

    for api_key in keys:
        status, body = attempt("v2_patch", "PATCH", v2_url, api_key, v2_body)
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(
                f"Pinned live {endpoint} to {image}. Image only. No VF_LAB. Did not PATCH lab.",
                flush=True,
            )
            return finish("pinned", " ".join(notes))

        status, body = attempt("v1_patch", "PATCH", v1_url, api_key, v1_body)
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(
                f"Pinned live {endpoint} to {image} via v1. Image only. No VF_LAB.",
                flush=True,
            )
            return finish("pinned", " ".join(notes))

    err = last_status if last_status else 403
    print(
        f"live fast pin HTTP {err}: {sanitize_detail(last_body[:200], secrets)}",
        flush=True,
    )
    return finish(f"error_{err}", f"{' '.join(notes)} {last_body[:200]}")
