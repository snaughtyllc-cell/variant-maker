"""PBKDF2 password hashes for invite-only Studio login. Stdlib only."""
from __future__ import annotations

import hashlib
import hmac
import secrets

MIN_PASSWORD_LENGTH = 8
_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 210_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password required")
    salt = secrets.token_hex(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS,
    )
    return f"{_SCHEME}${_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not password or not stored or not isinstance(stored, str):
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != _SCHEME:
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = parts[3]
    except (ValueError, TypeError):
        return False
    if iterations < 1:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(dk.hex(), expected)
