"""Workspace API keys for the public /api/v1 boundary.

JSON on the auth volume next to tenants.json — not inside job/media paths.
A digest of the full token is stored; plaintext is shown once at create.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from collections.abc import Iterable
from dataclasses import asdict, dataclass

ALL_SCOPES = frozenset({
    "jobs:create",
    "jobs:read",
    "gallery:read",
    "drive:export",
})
READ_SCOPES = frozenset({"jobs:read", "gallery:read"})
FULL_SCOPES = frozenset(ALL_SCOPES)
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 90
MIN_TTL_DAYS = 1
LABEL_MAX = 80
TOKEN_RE = re.compile(r"^vf_([0-9a-f]{16})_([0-9a-f]{64})$")
_DUMMY_DIGEST = hashlib.sha256(b"varimo-api-key-missing").hexdigest()


class ApiKeyStoreError(Exception):
    """Raised when the key file cannot be read. Callers must fail closed."""


@dataclass
class ApiKeyRecord:
    key_id: str
    workspace_id: str
    issuer_email: str
    label: str
    prefix: str
    digest: str
    scopes: list[str]
    created_utc: str
    expires_utc: str | None = None
    last_used_utc: str | None = None
    revoked_utc: str | None = None


@dataclass
class IssuedKey:
    record: ApiKeyRecord
    token: str


@dataclass
class ApiPrincipal:
    key_id: str
    workspace_id: str
    issuer_email: str
    scopes: frozenset[str]
    label: str = ""


def utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_token(token: str) -> tuple[str, str] | None:
    raw = (token or "").strip()
    m = TOKEN_RE.fullmatch(raw)
    if not m:
        return None
    return m.group(1), m.group(2)


def normalize_scopes(scopes: Iterable[str] | None, *, preset: str | None = None) -> list[str]:
    kind = (preset or "").strip().lower()
    if kind == "read":
        chosen = set(READ_SCOPES)
    elif kind == "full":
        chosen = set(FULL_SCOPES)
    else:
        chosen = {str(s).strip() for s in (scopes or []) if str(s).strip()}
    unknown = chosen - ALL_SCOPES
    if unknown:
        raise ValueError("unknown scope")
    if not chosen:
        raise ValueError("scopes required")
    return sorted(chosen)


def _parse_record(raw: object) -> ApiKeyRecord | None:
    if not isinstance(raw, dict):
        return None
    key_id = str(raw.get("key_id") or "").strip()
    workspace_id = str(raw.get("workspace_id") or "").strip()
    digest = str(raw.get("digest") or "").strip()
    if not key_id or not workspace_id or not digest:
        return None
    scopes = [
        str(s).strip() for s in (raw.get("scopes") or [])
        if str(s).strip() in ALL_SCOPES
    ]
    return ApiKeyRecord(
        key_id=key_id,
        workspace_id=workspace_id,
        issuer_email=str(raw.get("issuer_email") or "").strip().lower(),
        label=str(raw.get("label") or "").strip(),
        prefix=str(raw.get("prefix") or f"vf_{key_id}"),
        digest=digest,
        scopes=scopes,
        created_utc=str(raw.get("created_utc") or ""),
        expires_utc=str(raw.get("expires_utc") or "") or None,
        last_used_utc=str(raw.get("last_used_utc") or "") or None,
        revoked_utc=str(raw.get("revoked_utc") or "") or None,
    )


def public_key_dict(rec: ApiKeyRecord) -> dict:
    return {
        "key_id": rec.key_id,
        "label": rec.label,
        "prefix": rec.prefix,
        "scopes": list(rec.scopes),
        "created_utc": rec.created_utc,
        "expires_utc": rec.expires_utc,
        "last_used_utc": rec.last_used_utc,
        "revoked_utc": rec.revoked_utc,
    }


class ApiKeyStore:
    """JSON-file-backed key records. Missing file is empty; corrupt file fails closed."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def list_for_workspace(self, workspace_id: str) -> list[ApiKeyRecord]:
        ws = (workspace_id or "").strip()
        rows = [r for r in self._load() if r.workspace_id == ws]
        rows.sort(key=lambda r: (r.created_utc, r.key_id), reverse=True)
        return rows

    def get(self, key_id: str) -> ApiKeyRecord | None:
        kid = (key_id or "").strip()
        for rec in self._load():
            if rec.key_id == kid:
                return rec
        return None

    def create(
        self,
        *,
        workspace_id: str,
        issuer_email: str,
        label: str,
        scopes: Iterable[str],
        ttl_days: int = DEFAULT_TTL_DAYS,
        now: str | None = None,
    ) -> IssuedKey:
        name = (label or "").strip()
        if not name:
            raise ValueError("label required")
        if len(name) > LABEL_MAX:
            raise ValueError("label too long")
        days = int(ttl_days)
        if days < MIN_TTL_DAYS or days > MAX_TTL_DAYS:
            raise ValueError("expiry must be 1–90 days")
        granted = normalize_scopes(scopes)
        created = now or utc_now()
        expires_at = _dt.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.UTC)
        expires = (expires_at + _dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        key_id = secrets.token_hex(8)
        secret = secrets.token_hex(32)
        token = f"vf_{key_id}_{secret}"
        rec = ApiKeyRecord(
            key_id=key_id,
            workspace_id=workspace_id,
            issuer_email=(issuer_email or "").strip().lower(),
            label=name,
            prefix=f"vf_{key_id}",
            digest=token_digest(token),
            scopes=granted,
            created_utc=created,
            expires_utc=expires,
        )
        with self._lock:
            rows = self._load()
            rows.append(rec)
            self._save(rows)
        return IssuedKey(record=rec, token=token)

    def revoke(self, key_id: str, *, workspace_id: str, now: str | None = None) -> ApiKeyRecord | None:
        kid = (key_id or "").strip()
        ws = (workspace_id or "").strip()
        stamp = now or utc_now()
        with self._lock:
            rows = self._load()
            found: ApiKeyRecord | None = None
            for rec in rows:
                if rec.key_id != kid or rec.workspace_id != ws:
                    continue
                if not rec.revoked_utc:
                    rec.revoked_utc = stamp
                found = rec
                break
            if found is None:
                return None
            self._save(rows)
            return found

    def touch(self, key_id: str, *, now: str | None = None) -> None:
        kid = (key_id or "").strip()
        stamp = now or utc_now()
        with self._lock:
            rows = self._load()
            changed = False
            for rec in rows:
                if rec.key_id != kid:
                    continue
                rec.last_used_utc = stamp
                changed = True
                break
            if changed:
                self._save(rows)

    def authenticate(self, token: str, *, tenants) -> ApiKeyRecord | None:
        """Return a live key for this token, or None. Never raises on a bad token."""
        rows = self._load()
        parsed = parse_token(token)
        rec = None
        if parsed is not None:
            key_id, _secret = parsed
            rec = next((r for r in rows if r.key_id == key_id), None)
        digest = rec.digest if rec is not None else _DUMMY_DIGEST
        candidate = token_digest(token or "")
        try:
            matched = hmac.compare_digest(digest, candidate)
        except (TypeError, ValueError):
            return None
        if not matched:
            return None
        if rec is None or rec.revoked_utc:
            return None
        if rec.expires_utc and rec.expires_utc <= utc_now():
            return None
        if tenants is None:
            return None
        user = tenants.get_user(rec.issuer_email)
        if user is None or user.role != "owner" or user.workspace_id != rec.workspace_id:
            return None
        if tenants.get_workspace(rec.workspace_id) is None:
            return None
        return rec

    def _load(self) -> list[ApiKeyRecord]:
        if not os.path.isfile(self._path):
            return []
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ApiKeyStoreError("api key store unavailable") from exc
        if not isinstance(raw, dict):
            raise ApiKeyStoreError("api key store unavailable")
        items = raw.get("keys")
        if not isinstance(items, list):
            raise ApiKeyStoreError("api key store unavailable")
        out: list[ApiKeyRecord] = []
        for item in items:
            rec = _parse_record(item)
            if rec is None:
                raise ApiKeyStoreError("api key store unavailable")
            out.append(rec)
        return out

    def _save(self, rows: list[ApiKeyRecord]) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        payload = {"keys": [asdict(r) for r in rows]}
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".api-keys-", suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


def append_audit(path: str, record: dict) -> None:
    """Best-effort key-id audit. Never write tokens or Authorization."""
    row = dict(record)
    for banned in ("token", "authorization", "secret", "digest"):
        row.pop(banned, None)
    row.setdefault("utc", utc_now())
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        return
