"""Drive output layout: one subfolder per source clip, never a dump in the parent."""
import os


def source_output_subfolder(filename: str, sha: str) -> str:
    """`<stem>__<sha8>` — 10 inbox videos become 10 folders in the output parent."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip() or "source"
    stem = stem.replace("/", "_").replace("\\", "_")
    digest = (sha or "")[:8] or "unknown"
    return f"{stem}__{digest}"
