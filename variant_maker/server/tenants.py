"""Invite-only workspaces (JSON on the data volume). No Postgres this slice.

Auth is off until VARIANT_AUTH_ADMIN_EMAIL is set. Tests keep using a single
Workspace at the data-dir root.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from typing import Literal

from .plans import (
    PLAN_IDS,
    WINDOW_DAYS,
    QuotaSnapshot,
    fast_limit,
    hq_limit,
    normalize_plan,
)

InviteKind = Literal["join", "new_workspace"]
MemberRole = Literal["owner", "member"]
USAGE_KEEP_DAYS = 40

ADMIN_EMAIL_ENV = "VARIANT_AUTH_ADMIN_EMAIL"
LEGACY_DIR_NAMES = ("jobs", "drive", "uploads", "workflow-work")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_admin_email(email: str, admin_email: str | None) -> bool:
    if not admin_email:
        return False
    return normalize_email(email) == normalize_email(admin_email)


def auth_required(environ: dict | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return bool((env.get(ADMIN_EMAIL_ENV) or "").strip())


@dataclass
class WorkspaceInfo:
    id: str
    name: str
    created_utc: str
    plan: str = "internal"
    fast_limit_30d: int | None = None
    hq_limit_30d: int | None = None


@dataclass
class UserInfo:
    email: str
    name: str
    workspace_id: str
    role: MemberRole
    password_hash: str | None = None


@dataclass
class Invite:
    id: str
    email: str
    kind: InviteKind
    workspace_id: str | None
    created_utc: str


def _parse_user(raw: object, key: str = "") -> UserInfo | None:
    if not isinstance(raw, dict):
        return None
    email = normalize_email(str(raw.get("email") or key or ""))
    if not email:
        return None
    role = raw.get("role") if raw.get("role") in ("owner", "member") else "member"
    stored = raw.get("password_hash")
    password_hash = stored.strip() if isinstance(stored, str) and stored.strip() else None
    return UserInfo(
        email=email,
        name=str(raw.get("name") or email),
        workspace_id=str(raw.get("workspace_id") or ""),
        role=role,
        password_hash=password_hash,
    )


def _user_payload(user: UserInfo) -> dict:
    payload = {
        "email": user.email,
        "name": user.name,
        "workspace_id": user.workspace_id,
        "role": user.role,
    }
    if user.password_hash:
        payload["password_hash"] = user.password_hash
    return payload


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> _dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _dt.datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.UTC,
        )
    except ValueError:
        return None


def _opt_int(raw: dict, key: str) -> int | None:
    if key not in raw or raw[key] is None:
        return None
    try:
        return int(raw[key])
    except (TypeError, ValueError):
        return None


def _workspace_from_raw(raw: object, workspace_id: str) -> WorkspaceInfo | None:
    if not isinstance(raw, dict):
        return None
    return WorkspaceInfo(
        id=str(raw.get("id") or workspace_id),
        name=str(raw.get("name") or workspace_id),
        created_utc=str(raw.get("created_utc") or ""),
        plan=normalize_plan(raw.get("plan")),
        fast_limit_30d=_opt_int(raw, "fast_limit_30d"),
        hq_limit_30d=_opt_int(raw, "hq_limit_30d"),
    )


def _workspace_payload(ws: WorkspaceInfo, usage: list | None = None) -> dict:
    payload = {
        "id": ws.id,
        "name": ws.name,
        "created_utc": ws.created_utc,
        "plan": ws.plan,
    }
    if ws.fast_limit_30d is not None:
        payload["fast_limit_30d"] = ws.fast_limit_30d
    if ws.hq_limit_30d is not None:
        payload["hq_limit_30d"] = ws.hq_limit_30d
    if usage:
        payload["usage"] = usage
    return payload


def _usage_units(items: object, kind: str, *, now: _dt.datetime, window_days: int) -> int:
    if not isinstance(items, list):
        return 0
    cutoff = now - _dt.timedelta(days=window_days)
    total = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("kind") or "") != kind:
            continue
        when = _parse_utc(raw.get("utc"))
        if when is None or when < cutoff:
            continue
        try:
            total += max(0, int(raw.get("units") or 0))
        except (TypeError, ValueError):
            continue
    return total


def _prune_usage(items: object, *, now: _dt.datetime) -> list:
    if not isinstance(items, list):
        return []
    cutoff = now - _dt.timedelta(days=USAGE_KEEP_DAYS)
    kept = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        when = _parse_utc(raw.get("utc"))
        if when is None or when < cutoff:
            continue
        kept.append(raw)
    return kept


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class TenantStore:
    """One JSON file: workspaces, users, invites."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

    def _empty(self) -> dict:
        return {"workspaces": {}, "users": {}, "invites": []}

    def _load(self) -> dict:
        if not os.path.isfile(self._path):
            return self._empty()
        try:
            with open(self._path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return self._empty()
        if not isinstance(raw, dict):
            return self._empty()
        workspaces = raw.get("workspaces") if isinstance(raw.get("workspaces"), dict) else {}
        users = raw.get("users") if isinstance(raw.get("users"), dict) else {}
        invites = raw.get("invites") if isinstance(raw.get("invites"), list) else []
        return {"workspaces": workspaces, "users": users, "invites": invites}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self._path) or ".", prefix=".tenants-", suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def get_workspace(self, workspace_id: str) -> WorkspaceInfo | None:
        with self._lock:
            raw = self._load()["workspaces"].get(workspace_id)
        return _workspace_from_raw(raw, workspace_id)

    def get_user(self, email: str) -> UserInfo | None:
        key = normalize_email(email)
        with self._lock:
            raw = self._load()["users"].get(key)
        return _parse_user(raw, key)

    def list_invites(self) -> list[Invite]:
        with self._lock:
            items = list(self._load()["invites"])
        out: list[Invite] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            kind = raw.get("kind")
            if kind not in ("join", "new_workspace"):
                continue
            out.append(Invite(
                id=str(raw.get("id") or ""),
                email=normalize_email(str(raw.get("email") or "")),
                kind=kind,
                workspace_id=raw.get("workspace_id"),
                created_utc=str(raw.get("created_utc") or ""),
            ))
        return out

    def create_workspace(
        self, *, name: str, workspace_id: str | None = None, plan: str = "internal",
    ) -> WorkspaceInfo:
        ws = WorkspaceInfo(
            id=workspace_id or _new_id("ws"),
            name=name.strip() or "Workspace",
            created_utc=_now(),
            plan=normalize_plan(plan),
        )
        with self._lock:
            data = self._load()
            data["workspaces"][ws.id] = _workspace_payload(ws)
            self._save(data)
        return ws

    def set_workspace_plan(self, workspace_id: str, plan: str) -> WorkspaceInfo | None:
        if plan not in PLAN_IDS:
            raise ValueError("unknown plan")
        with self._lock:
            data = self._load()
            raw = data["workspaces"].get(workspace_id)
            ws = _workspace_from_raw(raw, workspace_id)
            if ws is None:
                return None
            usage = raw.get("usage") if isinstance(raw, dict) else []
            updated = WorkspaceInfo(
                id=ws.id,
                name=ws.name,
                created_utc=ws.created_utc,
                plan=plan,
                fast_limit_30d=ws.fast_limit_30d,
                hq_limit_30d=ws.hq_limit_30d,
            )
            data["workspaces"][workspace_id] = _workspace_payload(
                updated, usage if isinstance(usage, list) else [],
            )
            self._save(data)
        return updated

    def quota_snapshot(
        self, workspace_id: str, *, now: _dt.datetime | None = None,
    ) -> QuotaSnapshot:
        when = now or _dt.datetime.now(_dt.UTC)
        with self._lock:
            raw = self._load()["workspaces"].get(workspace_id)
        ws = _workspace_from_raw(raw, workspace_id)
        plan = normalize_plan(ws.plan if ws is not None else None)
        usage = raw.get("usage") if isinstance(raw, dict) else []
        return QuotaSnapshot(
            plan=plan,
            fast_used=_usage_units(usage, "fast", now=when, window_days=WINDOW_DAYS),
            fast_limit=fast_limit(plan, ws.fast_limit_30d if ws else None),
            hq_used=_usage_units(usage, "hq", now=when, window_days=WINDOW_DAYS),
            hq_limit=hq_limit(plan, ws.hq_limit_30d if ws else None),
            window_days=WINDOW_DAYS,
        )

    def record_usage(
        self,
        workspace_id: str,
        *,
        kind: str,
        units: int,
        job_id: str,
        utc: str | None = None,
    ) -> None:
        if units <= 0:
            return
        if kind not in ("fast", "hq"):
            return
        stamp = utc or _now()
        with self._lock:
            data = self._load()
            raw = data["workspaces"].get(workspace_id)
            ws = _workspace_from_raw(raw, workspace_id)
            if ws is None:
                return
            now = _parse_utc(stamp) or _dt.datetime.now(_dt.UTC)
            usage = _prune_usage(raw.get("usage") if isinstance(raw, dict) else [], now=now)
            usage.append({
                "utc": stamp,
                "kind": kind,
                "units": int(units),
                "job_id": job_id,
            })
            data["workspaces"][workspace_id] = _workspace_payload(ws, usage)
            self._save(data)

    def upsert_user(self, user: UserInfo) -> UserInfo:
        key = normalize_email(user.email)
        with self._lock:
            data = self._load()
            prev = _parse_user(data["users"].get(key), key)
            password_hash = user.password_hash
            if password_hash is None and prev is not None:
                password_hash = prev.password_hash
            stored = UserInfo(
                email=key,
                name=user.name or key,
                workspace_id=user.workspace_id,
                role=user.role,
                password_hash=password_hash,
            )
            data["users"][key] = _user_payload(stored)
            self._save(data)
        return stored

    def set_password(self, email: str, password_hash: str) -> UserInfo | None:
        user = self.get_user(email)
        if user is None:
            return None
        return self.upsert_user(UserInfo(
            email=user.email,
            name=user.name,
            workspace_id=user.workspace_id,
            role=user.role,
            password_hash=password_hash,
        ))

    def add_invite(self, *, email: str, kind: InviteKind,
                   workspace_id: str | None) -> Invite:
        addr = normalize_email(email)
        if not _EMAIL_RE.match(addr):
            raise ValueError("invalid email")
        if kind == "join" and not workspace_id:
            raise ValueError("join invite needs workspace_id")
        invite = Invite(
            id=_new_id("inv"), email=addr, kind=kind,
            workspace_id=workspace_id, created_utc=_now(),
        )
        with self._lock:
            data = self._load()
            # One pending invite per email.
            data["invites"] = [
                i for i in data["invites"]
                if not (isinstance(i, dict) and normalize_email(str(i.get("email") or "")) == addr)
            ]
            data["invites"].append(asdict(invite))
            self._save(data)
        return invite

    def delete_invite(self, invite_id: str) -> bool:
        with self._lock:
            data = self._load()
            before = len(data["invites"])
            data["invites"] = [
                i for i in data["invites"]
                if not (isinstance(i, dict) and str(i.get("id") or "") == invite_id)
            ]
            if len(data["invites"]) == before:
                return False
            self._save(data)
        return True

    def consume_invite(self, email: str) -> Invite | None:
        addr = normalize_email(email)
        with self._lock:
            data = self._load()
            found = None
            kept = []
            for raw in data["invites"]:
                if (
                    found is None
                    and isinstance(raw, dict)
                    and normalize_email(str(raw.get("email") or "")) == addr
                ):
                    kind = raw.get("kind")
                    if kind in ("join", "new_workspace"):
                        found = Invite(
                            id=str(raw.get("id") or ""),
                            email=addr,
                            kind=kind,
                            workspace_id=raw.get("workspace_id"),
                            created_utc=str(raw.get("created_utc") or ""),
                        )
                        continue
                kept.append(raw)
            if found is None:
                return None
            data["invites"] = kept
            self._save(data)
        return found

    def delete_user(self, email: str) -> bool:
        """Drop the login. Leaves workspace files in place. Also drops a pending invite."""
        key = normalize_email(email)
        with self._lock:
            data = self._load()
            if key not in data["users"]:
                return False
            del data["users"][key]
            data["invites"] = [
                i for i in data["invites"]
                if not (isinstance(i, dict) and normalize_email(str(i.get("email") or "")) == key)
            ]
            self._save(data)
        return True

    def list_workspace_ids(self) -> list[str]:
        with self._lock:
            return list(self._load()["workspaces"].keys())

    def list_users(self) -> list[UserInfo]:
        with self._lock:
            users = self._load()["users"]
        out: list[UserInfo] = []
        for key, raw in users.items():
            parsed = _parse_user(raw, str(key))
            if parsed is not None:
                out.append(parsed)
        return out

    def list_workspaces(self) -> list[WorkspaceInfo]:
        with self._lock:
            spaces = self._load()["workspaces"]
        out: list[WorkspaceInfo] = []
        for ws_id, raw in spaces.items():
            parsed = _workspace_from_raw(raw, str(ws_id))
            if parsed is not None:
                out.append(parsed)
        return out


def migrate_legacy_data(data_dir: str, workspace_id: str) -> bool:
    """Move root jobs/drive/uploads into tenants/{id}/. Returns True if anything moved."""
    root = os.path.abspath(data_dir)
    dest = os.path.join(root, "tenants", workspace_id)
    marker = os.path.join(root, "auth", "legacy_migrated")
    if os.path.isfile(marker):
        return False
    moved = False
    os.makedirs(dest, exist_ok=True)
    for name in LEGACY_DIR_NAMES:
        src = os.path.join(root, name)
        if not os.path.isdir(src):
            continue
        target = os.path.join(dest, name)
        if os.path.exists(target):
            continue
        shutil.move(src, target)
        moved = True
    os.makedirs(os.path.join(root, "auth"), exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(workspace_id + "\n")
    return moved


def tenant_root(data_dir: str, workspace_id: str) -> str:
    return os.path.join(os.path.abspath(data_dir), "tenants", workspace_id)


def provision_login(
    store: TenantStore,
    *,
    email: str,
    name: str,
    admin_email: str | None,
    data_dir: str | None = None,
) -> UserInfo | None:
    """Map a login email to a workspace. None = not invited."""
    addr = normalize_email(email)
    existing = store.get_user(addr)
    if existing is not None and existing.workspace_id:
        if name and name != existing.name:
            return store.upsert_user(UserInfo(
                email=existing.email, name=name,
                workspace_id=existing.workspace_id, role=existing.role,
            ))
        return existing

    if is_admin_email(addr, admin_email):
        ws = store.create_workspace(name=name or addr.split("@")[0] or "Studio")
        if data_dir:
            migrate_legacy_data(data_dir, ws.id)
        return store.upsert_user(UserInfo(
            email=addr, name=name or addr, workspace_id=ws.id, role="owner",
        ))

    invite = store.consume_invite(addr)
    if invite is None:
        return None
    if invite.kind == "join":
        ws_id = invite.workspace_id
        if not ws_id or store.get_workspace(ws_id) is None:
            return None
        return store.upsert_user(UserInfo(
            email=addr, name=name or addr, workspace_id=ws_id, role="member",
        ))
    ws = store.create_workspace(
        name=name or addr.split("@")[0] or "Studio", plan="creator",
    )
    return store.upsert_user(UserInfo(
        email=addr, name=name or addr, workspace_id=ws.id, role="owner",
    ))
