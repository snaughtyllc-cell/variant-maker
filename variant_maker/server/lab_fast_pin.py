"""Pin Lab Fast on Lab Studio boot. Never Live Fast."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence

LAB_FAST_ENDPOINT = "xar25v77v3j27u"
LIVE_FAST_ENDPOINT = "j0b1q4iuunzhnq"
DEFAULT_IMAGE = "ghcr.io/snaughtyllc-cell/variant-fast:lab"
_V2_PATCH_URL = "https://api.runpod.io/v2/serverless/{endpoint}"
_V1_ENDPOINT_URL = "https://rest.runpod.io/v1/endpoints/{endpoint}"
_V1_TEMPLATE_URL = "https://rest.runpod.io/v1/templates/{template_id}"
_GRAPHQL_URL = "https://api.runpod.io/graphql"
_USER_AGENT = "varyforge-lab-fast-pin/1"
_GHCR_TOKEN_URL = (
    "https://ghcr.io/token?service=ghcr.io"
    "&scope=repository:snaughtyllc-cell/variant-fast:pull"
)
_GHCR_MANIFEST_URL = "https://ghcr.io/v2/snaughtyllc-cell/variant-fast/manifests/lab"
_ENDPOINTS_QUERY = "query { myself { endpoints { id templateId } } }"
_SAVE_TEMPLATE = (
    "mutation ($id: String!, $imageName: String!, $name: String!, "
    "$disk: Int!) { saveTemplate(input: { id: $id, imageName: $imageName, "
    "name: $name, isServerless: true, volumeInGb: 0, "
    "containerDiskInGb: $disk }) { id imageName } }"
)
LAST_STATUS = "not_run"
LAST_DETAIL = ""

HttpFn = Callable[..., tuple[int, str]]
PatchFn = Callable[[str, str, str], tuple[int, str]]


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


def sanitize_detail(text: str, secrets: Sequence[str] = ()) -> str:
    """Health/log snippet: no live id, no API keys."""
    out = text or ""
    out = out.replace(LIVE_FAST_ENDPOINT, "[live]")
    out = re.sub(r"api_key=[^&\s\"']+", "api_key=[redacted]", out, flags=re.IGNORECASE)
    out = re.sub(r"(Bearer )\S+", r"\1[redacted]", out, flags=re.IGNORECASE)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return " ".join(out.split())[:240]


def _lab_only_template_id(endpoints: list) -> str | None:
    """Template id used by Lab Fast and by no other endpoint (especially Live)."""
    owners: dict[str, list[str]] = {}
    lab_tid = None
    for ep in endpoints:
        if not isinstance(ep, dict):
            continue
        eid = str(ep.get("id") or "").strip()
        tid = str(ep.get("templateId") or "").strip()
        if not tid:
            continue
        owners.setdefault(tid, []).append(eid)
        if eid == LAB_FAST_ENDPOINT:
            lab_tid = tid
    if not lab_tid or lab_tid == LIVE_FAST_ENDPOINT:
        return None
    users = owners.get(lab_tid) or []
    if set(users) != {LAB_FAST_ENDPOINT}:
        return None
    return lab_tid


def resolve_lab_image(
    environ: Mapping[str, str] | None = None,
    resolve_digest: Callable[[], str | None] | None = None,
    *,
    allow_network: bool = False,
) -> str:
    env = environ if environ is not None else os.environ
    raw = (env.get("VARIANT_LAB_FAST_IMAGE") or "").strip()
    if raw:
        return raw
    getter = resolve_digest
    if getter is None and allow_network:
        getter = _ghcr_lab_digest
    if getter is not None:
        digest = (getter() or "").strip()
        if (
            digest.startswith("sha256:")
            and len(digest) == 71
            and LIVE_FAST_ENDPOINT not in digest
        ):
            return f"ghcr.io/snaughtyllc-cell/variant-fast@{digest}"
    return DEFAULT_IMAGE


def _ghcr_lab_digest() -> str | None:
    try:
        req = urllib.request.Request(
            _GHCR_TOKEN_URL, headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        token = payload.get("token") or payload.get("access_token") or ""
        if not token:
            return None
        man = urllib.request.Request(
            _GHCR_MANIFEST_URL,
            headers={
                "User-Agent": _USER_AGENT,
                "Authorization": f"Bearer {token}",
                "Accept": (
                    "application/vnd.docker.distribution.manifest.v2+json, "
                    "application/vnd.oci.image.index.v1+json, "
                    "application/vnd.oci.image.manifest.v1+json"
                ),
            },
        )
        with urllib.request.urlopen(man, timeout=20) as resp:
            digest = (resp.headers.get("Docker-Content-Digest") or "").strip()
        return digest or None
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return None


def _management_keys(env: Mapping[str, str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for name in ("RUNPOD_ENDPOINT_UPDATE_KEY", "RUNPOD_API_KEY"):
        key = (env.get(name) or "").strip()
        if key and key not in seen:
            keys.append(key)
            seen.add(key)
    return keys


def _default_http(
    method: str,
    url: str,
    api_key: str,
    body: dict | None = None,
    *,
    graphql_query_key: bool = False,
) -> tuple[int, str]:
    if LIVE_FAST_ENDPOINT in url:
        return 0, "refused_live_url"
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if graphql_query_key:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}api_key={urllib.parse.quote(api_key, safe='')}"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
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


def _json_obj(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _graphql_ok(status: int, raw: str) -> bool:
    if not (200 <= status < 300):
        return False
    data = _json_obj(raw)
    if data.get("errors"):
        return False
    return bool(data.get("data"))


def pin_lab_fast_endpoint(
    environ: Mapping[str, str] | None = None,
    patch: PatchFn | None = None,
    http: HttpFn | None = None,
    resolve_digest: Callable[[], str | None] | None = None,
) -> str:
    env = environ if environ is not None else os.environ
    secrets: list[str] = []

    def finish(status: str, detail: str = "") -> str:
        global LAST_STATUS, LAST_DETAIL
        LAST_STATUS = status
        LAST_DETAIL = sanitize_detail(detail, secrets)
        return status

    endpoint = target_endpoint(env)
    if endpoint is None:
        if not _truthy(env.get("VARIANT_LAB")):
            return finish("skipped_not_lab")
        return finish("skipped_not_lab_endpoint")
    if endpoint == LIVE_FAST_ENDPOINT:
        return finish("skipped_not_lab_endpoint")
    keys = _management_keys(env)
    secrets.extend(keys)
    if not keys:
        return finish("skipped_no_key")
    allow_network = patch is None and http is None
    image = resolve_lab_image(
        env, resolve_digest, allow_network=allow_network
    )
    if LIVE_FAST_ENDPOINT in image:
        return finish("skipped_not_lab_endpoint")
    v2_url = _V2_PATCH_URL.format(endpoint=endpoint)
    v1_url = _V1_ENDPOINT_URL.format(endpoint=endpoint)
    if LIVE_FAST_ENDPOINT in v2_url or LIVE_FAST_ENDPOINT in v1_url:
        return finish("skipped_not_lab_endpoint")

    if patch is not None:
        status, body = patch(v2_url, keys[0], image)
        if status >= 300:
            print(
                f"lab fast pin HTTP {status}: {sanitize_detail(body[:200], secrets)}",
                flush=True,
            )
            return finish(f"error_{status}", f"v2_patch={status} {body[:200]}")
        print(f"Pinned lab {endpoint} to {image}. Did not PATCH live.", flush=True)
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
        *,
        graphql_query_key: bool = False,
    ) -> tuple[int, str]:
        if LIVE_FAST_ENDPOINT in url:
            notes.append(f"{label}=refused_live")
            return 0, "refused_live_url"
        status, text = do_http(
            method, url, api_key, body, graphql_query_key=graphql_query_key
        )
        notes.append(f"{label}={status}")
        return status, text

    for api_key in keys:
        status, body = attempt("v2_patch", "PATCH", v2_url, api_key, {"image": image})
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(f"Pinned lab {endpoint} to {image}. Did not PATCH live.", flush=True)
            return finish("pinned", " ".join(notes))

        status, body = attempt(
            "v1_patch", "PATCH", v1_url, api_key, {"imageName": image}
        )
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(f"Pinned lab {endpoint} to {image} via v1. Did not PATCH live.", flush=True)
            return finish("pinned", " ".join(notes))

        status, body = attempt(
            "v1_update", "POST", f"{v1_url}/update", api_key, {"imageName": image}
        )
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(f"Pinned lab {endpoint} to {image} via v1 update. Did not PATCH live.", flush=True)
            return finish("pinned", " ".join(notes))

        status, body = attempt("v1_get", "GET", v1_url, api_key)
        last_status, last_body = status, body

        lab_only = None
        for gql_label, use_query in (("gql_qs", True), ("gql_bearer", False)):
            status, body = attempt(
                gql_label,
                "POST",
                _GRAPHQL_URL,
                api_key,
                {"query": _ENDPOINTS_QUERY},
                graphql_query_key=use_query,
            )
            last_status, last_body = status, body
            if not _graphql_ok(status, body):
                continue
            payload = _json_obj(body)
            endpoints = (
                ((payload.get("data") or {}).get("myself") or {}).get("endpoints")
                or []
            )
            if not isinstance(endpoints, list):
                endpoints = []
            lab_only = _lab_only_template_id(endpoints)
            break

        if not lab_only or LIVE_FAST_ENDPOINT in lab_only:
            continue

        tpl_url = _V1_TEMPLATE_URL.format(template_id=lab_only)
        if LIVE_FAST_ENDPOINT in tpl_url:
            continue
        status, body = attempt(
            "tpl_patch", "PATCH", tpl_url, api_key, {"imageName": image}
        )
        last_status, last_body = status, body
        if 200 <= status < 300:
            print(
                f"Pinned lab template {lab_only} to {image}. Did not PATCH live.",
                flush=True,
            )
            return finish("pinned", " ".join(notes))

        tpl_name = "varyforge-fast-cpu-lab"
        disk = 10
        status, body = attempt("tpl_get", "GET", tpl_url, api_key)
        last_status, last_body = status, body
        if 200 <= status < 300:
            info = _json_obj(body)
            tpl_name = str(info.get("name") or tpl_name)
            try:
                disk = int(info.get("containerDiskInGb") or disk)
            except (TypeError, ValueError):
                disk = 10
        status, body = attempt(
            "gql_save",
            "POST",
            _GRAPHQL_URL,
            api_key,
            {
                "query": _SAVE_TEMPLATE,
                "variables": {
                    "id": lab_only,
                    "imageName": image,
                    "name": tpl_name,
                    "disk": disk,
                },
            },
            graphql_query_key=True,
        )
        last_status, last_body = status, body
        if _graphql_ok(status, body):
            print(
                f"Pinned lab template {lab_only} via GraphQL. Did not PATCH live.",
                flush=True,
            )
            return finish("pinned", " ".join(notes))

    err = last_status if last_status else 403
    print(
        f"lab fast pin HTTP {err}: {sanitize_detail(last_body[:200], secrets)}",
        flush=True,
    )
    return finish(
        f"error_{err}",
        f"{' '.join(notes)} {last_body[:200]}",
    )
