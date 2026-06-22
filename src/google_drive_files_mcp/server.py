"""MCP server: Google Drive file management (search, move, upload, folders) + Google Sheets editing, via stdio."""
from __future__ import annotations

import json
from collections.abc import Callable

from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from . import client, sheets
from .auth import DriveAuthError

mcp = FastMCP("google-drive-files")


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, indent=2)


def _run(fn: Callable[[], object]) -> str:
    """Run an operation and return its result as JSON, turning expected failures into a JSON error object."""
    try:
        return json.dumps(fn(), indent=2)
    except (DriveAuthError, ValueError, OSError) as e:
        return _err(str(e))
    except HttpError as e:
        return _err(f"Google API error: {e}")


# ============================================================ Drive: files

@mcp.tool()
def drive_search(query: str, only_folders: bool = False, max_results: int = 20) -> str:
    """Search Google Drive for files and/or folders. Use this to find an item to move and its destination folder.

    Args:
        query: Plain string (auto-wrapped as a filename search) or raw Drive query syntax.
        only_folders: If True, return only folders (handy for picking a destination).
        max_results: Max items to return. Clamped to [1, 100]. Default 20.

    Returns:
        JSON array of {id, name, mime_type, is_folder, parents, web_view_link}.
    """
    return _run(lambda: client.search(query, only_folders=only_folders, max_results=max_results))


@mcp.tool()
def drive_create_folder(name: str, parent: str | None = None) -> str:
    """Create a new folder in Google Drive.

    Args:
        name: The new folder's name.
        parent: Optional destination — folder ID, URL, 'root', or an unambiguous existing folder name.

    Returns:
        JSON {id, name, mime_type, is_folder, parents, web_view_link}.
    """
    return _run(lambda: client.create_folder(name, parent=parent))


@mcp.tool()
def drive_move(file: str, dest_folder: str, keep_existing_parents: bool = False) -> str:
    """Move a file or folder into a destination folder (true move — changes which folder it lives in).

    Args:
        file: The item to move — a Drive URL or file/folder ID.
        dest_folder: Destination — folder ID, URL, 'root', or an unambiguous existing folder name.
        keep_existing_parents: If True, ADD to dest_folder without removing it from its current folder(s).

    Returns:
        JSON {id, name, is_folder, moved_from, moved_to, parents_now, web_view_link}.
    """
    return _run(lambda: client.move(file, dest_folder, keep_existing_parents=keep_existing_parents))


@mcp.tool()
def drive_upload_file(local_path: str, parent: str | None = None, name: str | None = None,
                      mime_type: str | None = None) -> str:
    """Upload a local file (any type, including large binaries like zip/pdf/images) into Google Drive.

    Streams the bytes from the path via a resumable media upload, so file size and binary fidelity are not a
    problem. The file is stored as-is (no Google-format conversion).

    Args:
        local_path: Path to the local file to upload ('~' is expanded).
        parent: Destination folder — ID, URL, 'root', or an unambiguous existing folder name. Default: My Drive root.
        name: Name for the file in Drive. Default: the local file's basename.
        mime_type: Override the MIME type. Default: guessed from the filename, else application/octet-stream.

    Returns:
        JSON {id, name, mime_type, size_bytes, parents, web_view_link, local_path}.
    """
    return _run(lambda: client.upload_file(local_path, parent=parent, name=name, mime_type=mime_type))


# ============================================================ Sheets: inspect

@mcp.tool()
def sheets_get_info(spreadsheet: str) -> str:
    """List a spreadsheet's tabs and their sizes — call this first to learn the tab names and dimensions.

    Args:
        spreadsheet: A Google Sheets URL or a bare spreadsheet ID.

    Returns:
        JSON {spreadsheet_id, title, tabs: [{title, sheet_id, index, rows, cols}]}.
    """
    return _run(lambda: sheets.get_info(spreadsheet))


@mcp.tool()
def sheets_read(spreadsheet: str, range_a1: str, render_option: str = "FORMATTED_VALUE") -> str:
    """Read the values in an A1 range. Use this before writing so you can see what's there.

    Args:
        spreadsheet: Sheets URL or ID.
        range_a1: A1 range, e.g. 'Sheet1!A1:D10' or 'A1:D10' (defaults to the first tab if no tab is given).
        render_option: FORMATTED_VALUE (as shown) | UNFORMATTED_VALUE (raw numbers) | FORMULA (show formulas).

    Returns:
        JSON {range, values (2D array), rows, cols}.
    """
    return _run(lambda: sheets.read(spreadsheet, range_a1, render_option=render_option))


# ============================================================ Sheets: edit values

@mcp.tool()
def sheets_write(spreadsheet: str, range_a1: str, values: list[list], value_input_option: str = "USER_ENTERED") -> str:
    """Overwrite a range with new values. Returns the PRIOR contents (`before`) so the overwrite is auditable.

    Args:
        spreadsheet: Sheets URL or ID.
        range_a1: A1 range to write into, e.g. 'Sheet1!B2:B10'.
        values: 2D array of cell values (rows of columns), e.g. [[1],[2],[3]] or [["Q1", 100]].
        value_input_option: USER_ENTERED (parse numbers/dates, and '=SUM(..)' becomes a formula) | RAW (literal text).

    Returns:
        JSON {updated_range, updated_cells, updated_rows, updated_columns, before, after}.
    """
    return _run(lambda: sheets.write(spreadsheet, range_a1, values, value_input_option=value_input_option))


@mcp.tool()
def sheets_append(spreadsheet: str, range_a1: str, values: list[list], value_input_option: str = "USER_ENTERED") -> str:
    """Append rows after the last row of the table that `range_a1` belongs to (does not overwrite existing rows).

    Args:
        spreadsheet: Sheets URL or ID.
        range_a1: A range inside the target table, e.g. 'Sheet1!A1' or 'Sheet1!A:D'.
        values: 2D array of rows to append.
        value_input_option: USER_ENTERED | RAW.

    Returns:
        JSON {updated_range, appended_rows, updated_cells}.
    """
    return _run(lambda: sheets.append(spreadsheet, range_a1, values, value_input_option=value_input_option))


@mcp.tool()
def sheets_clear(spreadsheet: str, range_a1: str) -> str:
    """Clear the VALUES in a range (formatting is left intact). Returns the prior contents under `before`.

    Args:
        spreadsheet: Sheets URL or ID.
        range_a1: A1 range to clear, e.g. 'Sheet1!A2:D100'.

    Returns:
        JSON {cleared_range, before}.
    """
    return _run(lambda: sheets.clear(spreadsheet, range_a1))


@mcp.tool()
def sheets_batch_write(spreadsheet: str, updates: list[dict], value_input_option: str = "USER_ENTERED") -> str:
    """Write several ranges in one atomic call.

    Args:
        spreadsheet: Sheets URL or ID.
        updates: list of {"range": "<A1>", "values": [[...]]} objects.
        value_input_option: USER_ENTERED | RAW.

    Returns:
        JSON {total_updated_cells, total_updated_ranges}.
    """
    return _run(lambda: sheets.batch_write(spreadsheet, updates, value_input_option=value_input_option))


# ============================================================ Sheets: structure

@mcp.tool()
def sheets_add_tab(spreadsheet: str, title: str, rows: int = 1000, cols: int = 26) -> str:
    """Add a new tab (sheet) to a spreadsheet.

    Returns:
        JSON {sheet_id, title, rows, cols}.
    """
    return _run(lambda: sheets.add_tab(spreadsheet, title, rows=rows, cols=cols))


@mcp.tool()
def sheets_rename_tab(spreadsheet: str, tab: str, new_title: str) -> str:
    """Rename a tab. `tab` is the current tab title (or its numeric sheetId as a string).

    Returns:
        JSON {sheet_id, old_title, new_title}.
    """
    return _run(lambda: sheets.rename_tab(spreadsheet, tab, new_title))


@mcp.tool()
def sheets_delete_tab(spreadsheet: str, tab: str) -> str:
    """Delete a tab (DESTRUCTIVE). `tab` is the tab title (or its numeric sheetId as a string).

    Returns:
        JSON {deleted_sheet_id, deleted_title}.
    """
    return _run(lambda: sheets.delete_tab(spreadsheet, tab))


# ============================================================ Sheets: formatting

@mcp.tool()
def sheets_format(spreadsheet: str, range_a1: str, number_format: str | None = None,
                  bold: bool | None = None, background: str | None = None) -> str:
    """Format a range: number pattern, bold, and/or background colour. Pass at least one.

    Args:
        spreadsheet: Sheets URL or ID.
        range_a1: A1 range, e.g. 'Sheet1!B2:B10'.
        number_format: A number pattern, e.g. '#,##0.00', '0.00%', '$#,##0.00'.
        bold: True/False to set bold.
        background: Cell background as '#RRGGBB'.

    Returns:
        JSON {sheet_id, range, applied}.
    """
    return _run(lambda: sheets.format_cells(spreadsheet, range_a1, number_format=number_format,
                                            bold=bold, background=background))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
