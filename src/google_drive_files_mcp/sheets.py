"""Google Sheets editing operations — granular, single-purpose functions (values, structure, formatting).

Each write returns enough context (before/after, counts) to be auditable. The full `drive` scope already
authorizes the Sheets API; the Sheets API must be enabled on the OAuth client's Google Cloud project.
"""
from __future__ import annotations

import re

from .auth import sheets_service
from .client import (
    extract_file_id,  # reuses /d/<id> URL + bare-id extraction (works for Sheets URLs too)
)

_COL_RE = re.compile(r"^[A-Za-z]*$")
_ROW_RE = re.compile(r"^\d*$")


def spreadsheet_id(spreadsheet: str) -> str:
    """Accept a Sheets URL or a bare spreadsheet ID."""
    return extract_file_id(spreadsheet)


# ---------------------------------------------------------------- pure helpers

def col_to_index(letters: str) -> int:
    """'A'->0, 'Z'->25, 'AA'->26. Raises on empty/invalid."""
    if not letters or not _COL_RE.match(letters):
        raise ValueError(f"invalid column letters: {letters!r}")
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def hex_to_rgb(hex_color: str) -> dict:
    """'#RRGGBB' (or 'RRGGBB') -> {red, green, blue} floats in [0, 1]."""
    h = hex_color.strip().lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(f"invalid hex color: {hex_color!r} (expected #RRGGBB)")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return {"red": r, "green": g, "blue": b}


def parse_a1(a1: str) -> dict:
    """Parse an A1 range into 0-based, end-exclusive bounds. Open ends are None.

    Returns {sheet, start_row, end_row, start_col, end_col}. Handles 'A1', 'A1:C5',
    'Sheet1!B2:D4', 'A:C' (whole columns), '2:5' (whole rows).
    """
    s = (a1 or "").strip()
    if not s:
        raise ValueError("empty A1 range")
    sheet = None
    if "!" in s:
        sheet, s = s.split("!", 1)
        sheet = sheet.strip().strip("'")
    if ":" in s:
        a, b = s.split(":", 1)
    else:
        a = b = s

    def _split(part: str) -> tuple[str, str]:
        m = re.match(r"^([A-Za-z]*)(\d*)$", part.strip())
        if not m or part.strip() == "":
            raise ValueError(f"unparseable A1 cell {part!r} in {a1!r}")
        return m.group(1), m.group(2)

    ca, ra = _split(a)
    cb, rb = _split(b)
    start_col = col_to_index(ca) if ca else None
    end_col = (col_to_index(cb) + 1) if cb else None
    start_row = (int(ra) - 1) if ra else None
    end_row = int(rb) if rb else None
    return {"sheet": sheet, "start_row": start_row, "end_row": end_row,
            "start_col": start_col, "end_col": end_col}


# ---------------------------------------------------------------- inspect

def get_info(spreadsheet: str) -> dict:
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    meta = svc.spreadsheets().get(
        spreadsheetId=ssid,
        fields="properties.title,sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)))",
    ).execute()
    tabs = []
    for sh in meta.get("sheets", []):
        p = sh.get("properties", {})
        grid = p.get("gridProperties", {})
        tabs.append({
            "title": p.get("title", ""),
            "sheet_id": p.get("sheetId"),
            "index": p.get("index"),
            "rows": grid.get("rowCount"),
            "cols": grid.get("columnCount"),
        })
    return {"spreadsheet_id": ssid, "title": meta.get("properties", {}).get("title", ""), "tabs": tabs}


def read(spreadsheet: str, range_a1: str, render_option: str = "FORMATTED_VALUE") -> dict:
    """Read a range. render_option: FORMATTED_VALUE | UNFORMATTED_VALUE | FORMULA."""
    svc = sheets_service()
    resp = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id(spreadsheet), range=range_a1, valueRenderOption=render_option,
    ).execute()
    vals = resp.get("values", [])
    return {"range": resp.get("range", range_a1), "values": vals,
            "rows": len(vals), "cols": max((len(r) for r in vals), default=0)}


# ---------------------------------------------------------------- edit values

def write(spreadsheet: str, range_a1: str, values: list[list], value_input_option: str = "USER_ENTERED") -> dict:
    """Overwrite a range with `values` (2D). value_input_option: USER_ENTERED (parse numbers/formulas) | RAW.

    Returns the prior contents under `before` so the overwrite is auditable.
    """
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    before = svc.spreadsheets().values().get(spreadsheetId=ssid, range=range_a1).execute().get("values", [])
    resp = svc.spreadsheets().values().update(
        spreadsheetId=ssid, range=range_a1, valueInputOption=value_input_option, body={"values": values},
    ).execute()
    return {
        "updated_range": resp.get("updatedRange"),
        "updated_cells": resp.get("updatedCells"),
        "updated_rows": resp.get("updatedRows"),
        "updated_columns": resp.get("updatedColumns"),
        "before": before,
        "after": values,
    }


def append(spreadsheet: str, range_a1: str, values: list[list], value_input_option: str = "USER_ENTERED") -> dict:
    """Append rows after the last row of the table that `range_a1` falls in (INSERT_ROWS)."""
    svc = sheets_service()
    resp = svc.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id(spreadsheet), range=range_a1,
        valueInputOption=value_input_option, insertDataOption="INSERT_ROWS", body={"values": values},
    ).execute()
    upd = resp.get("updates", {})
    return {"updated_range": upd.get("updatedRange"), "appended_rows": upd.get("updatedRows"),
            "updated_cells": upd.get("updatedCells")}


def clear(spreadsheet: str, range_a1: str) -> dict:
    """Clear the VALUES in a range (formatting is left intact). Returns prior contents under `before`."""
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    before = svc.spreadsheets().values().get(spreadsheetId=ssid, range=range_a1).execute().get("values", [])
    resp = svc.spreadsheets().values().clear(spreadsheetId=ssid, range=range_a1, body={}).execute()
    return {"cleared_range": resp.get("clearedRange"), "before": before}


def batch_write(spreadsheet: str, updates: list[dict], value_input_option: str = "USER_ENTERED") -> dict:
    """Write multiple ranges atomically. `updates` = [{"range": "A1:B2", "values": [[...]]}, ...]."""
    svc = sheets_service()
    data = [{"range": u["range"], "values": u["values"]} for u in updates]
    resp = svc.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id(spreadsheet),
        body={"valueInputOption": value_input_option, "data": data},
    ).execute()
    return {"total_updated_cells": resp.get("totalUpdatedCells"),
            "total_updated_ranges": len(resp.get("responses", []))}


# ---------------------------------------------------------------- structure

def _resolve_sheet_id(svc, ssid: str, tab) -> tuple[int, str]:
    """Resolve a tab given a numeric sheetId or a tab title. Returns (sheet_id, title)."""
    meta = svc.spreadsheets().get(
        spreadsheetId=ssid, fields="sheets(properties(sheetId,title))").execute()
    sheets = [s["properties"] for s in meta.get("sheets", [])]
    if isinstance(tab, int) or (isinstance(tab, str) and tab.isdigit()):
        sid = int(tab)
        for p in sheets:
            if p["sheetId"] == sid:
                return p["sheetId"], p["title"]
        raise ValueError(f"no tab with sheetId {sid}")
    matches = [p for p in sheets if p["title"] == tab]
    if len(matches) == 1:
        return matches[0]["sheetId"], matches[0]["title"]
    if not matches:
        raise ValueError(f"no tab named {tab!r}; tabs: {[p['title'] for p in sheets]}")
    raise ValueError(f"multiple tabs named {tab!r} — pass the numeric sheetId instead")


def add_tab(spreadsheet: str, title: str, rows: int = 1000, cols: int = 26) -> dict:
    svc = sheets_service()
    resp = svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id(spreadsheet),
        body={"requests": [{"addSheet": {"properties": {
            "title": title, "gridProperties": {"rowCount": rows, "columnCount": cols}}}}]},
    ).execute()
    props = resp["replies"][0]["addSheet"]["properties"]
    return {"sheet_id": props["sheetId"], "title": props["title"], "rows": rows, "cols": cols}


def rename_tab(spreadsheet: str, tab, new_title: str) -> dict:
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    sid, old_title = _resolve_sheet_id(svc, ssid, tab)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=ssid,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sid, "title": new_title}, "fields": "title"}}]},
    ).execute()
    return {"sheet_id": sid, "old_title": old_title, "new_title": new_title}


def delete_tab(spreadsheet: str, tab) -> dict:
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    sid, title = _resolve_sheet_id(svc, ssid, tab)
    svc.spreadsheets().batchUpdate(
        spreadsheetId=ssid, body={"requests": [{"deleteSheet": {"sheetId": sid}}]},
    ).execute()
    return {"deleted_sheet_id": sid, "deleted_title": title}


# ---------------------------------------------------------------- formatting

def format_cells(spreadsheet: str, range_a1: str, number_format: str | None = None,
                 bold: bool | None = None, background: str | None = None) -> dict:
    """Apply number format (pattern, e.g. '#,##0.00' / '0.00%' / '$#,##0'), bold, and/or background (#RRGGBB)."""
    if number_format is None and bold is None and background is None:
        raise ValueError("nothing to format — pass at least one of number_format, bold, background")
    svc = sheets_service()
    ssid = spreadsheet_id(spreadsheet)
    rng = parse_a1(range_a1)
    sid, _title = _resolve_sheet_id(svc, ssid, rng["sheet"]) if rng["sheet"] else _resolve_sheet_id(svc, ssid, _first_tab(svc, ssid))

    grid = {"sheetId": sid}
    if rng["start_row"] is not None:
        grid["startRowIndex"] = rng["start_row"]
    if rng["end_row"] is not None:
        grid["endRowIndex"] = rng["end_row"]
    if rng["start_col"] is not None:
        grid["startColumnIndex"] = rng["start_col"]
    if rng["end_col"] is not None:
        grid["endColumnIndex"] = rng["end_col"]

    cell_format: dict = {}
    fields = []
    if number_format is not None:
        cell_format["numberFormat"] = {"type": "NUMBER", "pattern": number_format}
        fields.append("userEnteredFormat.numberFormat")
    if bold is not None:
        cell_format["textFormat"] = {"bold": bold}
        fields.append("userEnteredFormat.textFormat.bold")
    if background is not None:
        cell_format["backgroundColor"] = hex_to_rgb(background)
        fields.append("userEnteredFormat.backgroundColor")

    svc.spreadsheets().batchUpdate(
        spreadsheetId=ssid,
        body={"requests": [{"repeatCell": {
            "range": grid,
            "cell": {"userEnteredFormat": cell_format},
            "fields": ",".join(fields),
        }}]},
    ).execute()
    return {"sheet_id": sid, "range": range_a1, "applied": fields}


def _first_tab(svc, ssid: str) -> str:
    meta = svc.spreadsheets().get(spreadsheetId=ssid, fields="sheets(properties(title))").execute()
    return meta["sheets"][0]["properties"]["title"]
