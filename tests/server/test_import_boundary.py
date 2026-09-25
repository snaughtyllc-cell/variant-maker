"""Import-boundary canary: engine modules must not import server-side heavy deps."""
from __future__ import annotations

import os

# Heavy deps that must ONLY appear under variant_maker/server/
_FORBIDDEN = ("fastapi", "uvicorn", "sse_starlette", "starlette")


def _engine_py_files() -> list[str]:
    """Return absolute paths of all *.py files under variant_maker/ excluding variant_maker/server/."""
    base = os.path.join(os.path.dirname(__file__), "..", "..", "variant_maker")
    base = os.path.abspath(base)
    server_prefix = os.path.join(base, "server")
    result = []
    for dirpath, _dirnames, filenames in os.walk(base):
        if dirpath == server_prefix or dirpath.startswith(server_prefix + os.sep):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                result.append(os.path.join(dirpath, fn))
    return result


def test_engine_does_not_import_server_deps() -> None:
    """No core engine module may import fastapi/uvicorn/sse_starlette/starlette."""
    violations: list[str] = []
    for path in _engine_py_files():
        with open(path, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        for dep in _FORBIDDEN:
            # Match bare `import dep` or `from dep` lines (or `dep.` sub-imports)
            if f"import {dep}" in source or f"from {dep}" in source:
                violations.append(f"{path}: imports '{dep}'")
    assert not violations, "Engine modules must not import server deps:\n" + "\n".join(violations)
