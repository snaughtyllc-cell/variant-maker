from __future__ import annotations
import re
from urllib.parse import urlparse

class DriveUrlError(ValueError):
    """Raised when a pasted Drive link is not a usable folder id."""

_FOLDER_PATH = re.compile(
    r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)",
)
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_FILE_PATH = re.compile(r"/file/d/")


def parse_folder_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if not s:
        raise DriveUrlError("empty Drive folder link")
    if _FILE_PATH.search(s):
        raise DriveUrlError("expected a Drive folder link, not a file link")
    if _BARE_ID.match(s) and "://" not in s:
        return s
    path = urlparse(s).path if "://" in s else s
    m = _FOLDER_PATH.search(path)
    if not m:
        raise DriveUrlError("could not parse Drive folder id from link")
    return m.group(1)
