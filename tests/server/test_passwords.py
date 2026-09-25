"""PBKDF2 password hashes — no plaintext, no extra deps."""
from variant_maker.server.passwords import hash_password, verify_password


def test_hash_roundtrip_and_wrong_password():
    stored = hash_password("correct-horse")
    assert stored.startswith("pbkdf2_sha256$")
    assert "correct-horse" not in stored
    assert verify_password("correct-horse", stored) is True
    assert verify_password("wrong-password", stored) is False
    assert verify_password("correct-horse", None) is False
    assert verify_password("", stored) is False
    assert verify_password("correct-horse", "not-a-hash") is False
