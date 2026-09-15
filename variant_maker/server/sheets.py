"""Google Sheets client seam for the Drop Ledger (fakes in tests; real API on Pod)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
# Create spreadsheet files in the connected user's Drive.
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"

SHEET_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    SHEETS_SCOPE,
]


class SheetsClient(ABC):
    """Minimal surface: create a spreadsheet, read/write a range, append rows."""

    @abstractmethod
    def create_spreadsheet(self, title: str) -> str:
        """Create a spreadsheet owned by the connected user; return spreadsheet id."""

    @abstractmethod
    def get_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:
        """Return cell values for `range_a1` (empty cells as "")."""

    @abstractmethod
    def update_values(self, spreadsheet_id: str, range_a1: str, values: Sequence[Sequence[str]]) -> None:
        """Overwrite `range_a1` with `values` (USER_ENTERED)."""

    @abstractmethod
    def append_values(self, spreadsheet_id: str, range_a1: str, values: Sequence[Sequence[str]]) -> None:
        """Append rows after the last non-empty row in the sheet tab of `range_a1`."""


class FakeSheets(SheetsClient):
    """In-memory Sheets double for unit tests."""

    def __init__(self) -> None:
        self.spreadsheets: dict[str, list[list[str]]] = {}
        self._next_id = 1
        self.created_titles: list[str] = []

    def create_spreadsheet(self, title: str) -> str:
        sid = f"sheet-{self._next_id}"
        self._next_id += 1
        self.spreadsheets[sid] = []
        self.created_titles.append(title)
        return sid

    def get_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:
        rows = self.spreadsheets.get(spreadsheet_id)
        if rows is None:
            raise KeyError(f"unknown spreadsheet: {spreadsheet_id}")
        return [list(r) for r in rows]

    def update_values(self, spreadsheet_id: str, range_a1: str, values: Sequence[Sequence[str]]) -> None:
        if spreadsheet_id not in self.spreadsheets:
            raise KeyError(f"unknown spreadsheet: {spreadsheet_id}")
        # MVP: treat range as full-sheet rewrite when A1 or Sheet1!A1; else pad/overwrite from row 1.
        start_row = _a1_start_row(range_a1) - 1
        sheet = self.spreadsheets[spreadsheet_id]
        while len(sheet) < start_row:
            sheet.append([])
        for i, row in enumerate(values):
            idx = start_row + i
            while len(sheet) <= idx:
                sheet.append([])
            sheet[idx] = [str(c) for c in row]

    def append_values(self, spreadsheet_id: str, range_a1: str, values: Sequence[Sequence[str]]) -> None:
        if spreadsheet_id not in self.spreadsheets:
            raise KeyError(f"unknown spreadsheet: {spreadsheet_id}")
        sheet = self.spreadsheets[spreadsheet_id]
        for row in values:
            sheet.append([str(c) for c in row])


def _a1_start_row(range_a1: str) -> int:
    """Best-effort row number from A1 like 'Sheet1!A2' or 'A1' (default 1)."""
    import re

    m = re.search(r"[A-Za-z]+(\d+)", range_a1.split("!")[-1])
    return int(m.group(1)) if m else 1


class GoogleSheets(SheetsClient):
    """Real Sheets + Drive create. Lazy-imports google libs ([farm] extra)."""

    def __init__(self, *, oauth_token: str | None = None, service=None, drive_service=None):
        self._oauth_token = oauth_token
        self._service = service
        self._drive = drive_service

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_sheets()
        return self._service

    @property
    def drive(self):
        if self._drive is None:
            self._drive = self._build_drive()
        return self._drive

    def _creds(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        if not self._oauth_token:
            raise ValueError("GoogleSheets needs oauth_token path")
        creds = Credentials.from_authorized_user_file(self._oauth_token, SHEET_SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
        return creds

    def _build_sheets(self):  # pragma: no cover - needs google libs + creds
        from googleapiclient.discovery import build

        return build("sheets", "v4", credentials=self._creds(), cache_discovery=False)

    def _build_drive(self):  # pragma: no cover - needs google libs + creds
        from googleapiclient.discovery import build

        return build("drive", "v3", credentials=self._creds(), cache_discovery=False)

    def create_spreadsheet(self, title: str) -> str:  # pragma: no cover
        body = {"properties": {"title": title}}
        res = self.service.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        return res["spreadsheetId"]

    def get_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:  # pragma: no cover
        res = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_a1,
        ).execute()
        rows = res.get("values") or []
        return [[str(c) for c in row] for row in rows]

    def update_values(self, spreadsheet_id: str, range_a1: str,
                      values: Sequence[Sequence[str]]) -> None:  # pragma: no cover
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption="USER_ENTERED",
            body={"values": [list(r) for r in values]},
        ).execute()

    def append_values(self, spreadsheet_id: str, range_a1: str,
                      values: Sequence[Sequence[str]]) -> None:  # pragma: no cover
        self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [list(r) for r in values]},
        ).execute()
