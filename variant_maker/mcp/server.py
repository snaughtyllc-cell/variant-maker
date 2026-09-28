"""stdio MCP server. Host launches this process; logs go to stderr only."""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from variant_maker.mcp.client import StudioV1Client, StudioV1Error

TOOL_NAMES = (
    "list_folders",
    "list_clips",
    "create_pack",
    "get_pack",
    "list_gallery",
    "send_to_drive",
)

_LOG = logging.getLogger("varimo_mcp")


def send_to_drive_args(
    *,
    export_id: str | None = None,
    destination_id: str | None = None,
    variants: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> tuple[str, Any]:
    """Mutually exclusive: status (`export_id`) or submit (destination + copies)."""
    export = (export_id or "").strip() or None
    dest = (destination_id or "").strip() or None
    req = (request_id or "").strip() or None
    refs = [dict(v) for v in (variants or [])]
    if export:
        if dest or refs or req:
            raise ValueError("export_id cannot be combined with submit fields")
        return "status", export
    if not dest or not refs or not req:
        raise ValueError("destination_id, variants, and request_id required")
    return "submit", {"destination_id": dest, "variants": refs, "request_id": req}


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def build_server(*, client: StudioV1Client | None = None) -> FastMCP:
    studio = client or StudioV1Client.from_env()
    mcp = FastMCP(
        "varimo",
        instructions=(
            "Give only the API key. Call list_folders, pick Inbox and Out by name, "
            "call list_clips on Inbox, then create_pack. Do not ask the operator for "
            "destination ids or Drive file ids. Review look in Studio Gallery before "
            "send_to_drive. We do not post."
        ),
    )

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    def list_folders() -> str:
        """Names of Drive folders already on this workspace. Pick Inbox / Out by name."""
        try:
            return _dump(studio.list_folders())
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    def list_clips(destination_id: str) -> str:
        """Videos in one folder from list_folders. Names only — pick a clip, then create_pack."""
        try:
            return _dump(studio.list_clips(destination_id))
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    def create_pack(
        input_destination_id: str,
        drive_file_id: str,
        count: int,
        request_id: str,
    ) -> str:
        """Start one Fast pack. Does not wait for copies. Reuse request_id to retry."""
        try:
            return _dump(studio.create_pack(
                input_destination_id=input_destination_id,
                drive_file_id=drive_file_id,
                count=count,
                request_id=request_id,
            ))
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    def get_pack(pack_id: str) -> str:
        """Pack state, ready counts, copy indexes. Review look at review_url in Studio."""
        try:
            return _dump(studio.get_pack(pack_id))
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    def list_gallery(
        pack_id: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> str:
        """Safe Gallery metadata page. Names and counts only — not a look review."""
        try:
            return _dump(studio.list_gallery(pack_id=pack_id, limit=limit, cursor=cursor))
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    def send_to_drive(
        export_id: str | None = None,
        destination_id: str | None = None,
        variants: list[dict[str, Any]] | None = None,
        request_id: str | None = None,
    ) -> str:
        """Export selected ready copies, or poll an export_id. Mutually exclusive."""
        try:
            kind, payload = send_to_drive_args(
                export_id=export_id,
                destination_id=destination_id,
                variants=variants,
                request_id=request_id,
            )
            if kind == "status":
                return _dump(studio.get_export(payload))
            return _dump(studio.create_export(**payload))
        except (StudioV1Error, ValueError) as exc:
            raise RuntimeError(str(exc)) from exc

    return mcp


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="varimo-mcp %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _LOG.info("stdio; set VARIMO_BASE_URL and VARIMO_API_KEY; never paste the key into chat")
    build_server().run()


if __name__ == "__main__":
    main()
