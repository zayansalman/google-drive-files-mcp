"""MCP server: exposes Google Drive file-management tools (move, create folder, search) via stdio."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import client
from .auth import DriveAuthError

mcp = FastMCP("google-drive-files")


def _err(msg: str) -> str:
    return json.dumps({"error": msg}, indent=2)


@mcp.tool()
def drive_search(query: str, only_folders: bool = False, max_results: int = 20) -> str:
    """Search Google Drive for files and/or folders. Use this to find the item to move and its destination folder.

    Args:
        query: Plain string (auto-wrapped as a filename search) or raw Drive query syntax.
        only_folders: If True, return only folders (handy for picking a move destination).
        max_results: Max items to return. Clamped to [1, 100]. Default 20.

    Returns:
        JSON array of {id, name, mime_type, is_folder, parents, web_view_link}.
    """
    try:
        return json.dumps(client.search(query, only_folders=only_folders, max_results=max_results), indent=2)
    except DriveAuthError as e:
        return _err(str(e))


@mcp.tool()
def drive_create_folder(name: str, parent: str | None = None) -> str:
    """Create a new folder in Google Drive.

    Args:
        name: The new folder's name.
        parent: Optional destination — a folder ID, URL, 'root', or an unambiguous existing folder name.
                If omitted, the folder is created in My Drive root.

    Returns:
        JSON {id, name, mime_type, is_folder, parents, web_view_link} for the created folder.
    """
    try:
        return json.dumps(client.create_folder(name, parent=parent), indent=2)
    except DriveAuthError as e:
        return _err(str(e))
    except ValueError as e:
        return _err(str(e))


@mcp.tool()
def drive_move(file: str, dest_folder: str, keep_existing_parents: bool = False) -> str:
    """Move a file or folder into a destination folder (true move — changes which folder it lives in).

    Args:
        file: The item to move — a Drive URL or file/folder ID.
        dest_folder: Destination — a folder ID, URL, 'root', or an unambiguous existing folder name.
        keep_existing_parents: If True, ADD the item to dest_folder without removing it from its current
                               folder(s) (Drive items can live in multiple folders). Default False = true move.

    Returns:
        JSON {id, name, is_folder, moved_from, moved_to, parents_now, web_view_link}.
    """
    try:
        return json.dumps(
            client.move(file, dest_folder, keep_existing_parents=keep_existing_parents), indent=2
        )
    except DriveAuthError as e:
        return _err(str(e))
    except ValueError as e:
        return _err(str(e))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
