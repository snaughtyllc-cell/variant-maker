from variant_maker.server.login_limit import (
    MAX_FAILURES,
    clear,
    locked,
    note_failure,
    reset,
)


def test_login_limit_locks_after_max_failures():
    reset()
    key = "ops@x.com"
    assert locked(key) is False
    now = 1_000_000.0
    for i in range(MAX_FAILURES):
        note_failure(key, now=now + i)
    assert locked(key, now=now + MAX_FAILURES) is True
    clear(key)
    assert locked(key, now=now + MAX_FAILURES) is False
    reset()


def test_login_limit_is_per_key():
    reset()
    now = 3_000_000.0
    for i in range(MAX_FAILURES):
        note_failure("jeff@x.com|1.1.1.1", now=now + i)
    assert locked("jeff@x.com|1.1.1.1", now=now + MAX_FAILURES) is True
    assert locked("jeff@x.com|9.9.9.9", now=now + MAX_FAILURES) is False
    reset()


def test_login_limit_expires_with_window():
    reset()
    key = "va@x.com"
    now = 2_000_000.0
    for i in range(MAX_FAILURES):
        note_failure(key, now=now)
    assert locked(key, now=now + 1) is True
    assert locked(key, now=now + 15 * 60 + 1) is False
    reset()
