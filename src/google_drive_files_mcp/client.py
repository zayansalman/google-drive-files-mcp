"""Google Drive file-management operations: search, create folder, move (change parents), upload."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import TypedDict

from googleapiclient.http import MediaFileUpload

from .auth import service

FOLDER_MIME = "application/vnd.google-apps.folder"

_FILE_ID_IN_PATH = re.compile(r"/d/([a-zA-Z0-9_-]{10,})")
_FILE_ID_IN_QUERY = re.compile(r"[?&]id=([a-zA-Z0-9_-]{10,})")
# A bare Drive ID is long and mixed; require >=25 chars so we don't mistake a
# folder *name* (e.g. "ProjectAlpha") for an ID during destination resolution.
_LIKELY_BARE_ID = re.compile(r"^[a-zA-Z0-9_-]{25,}$")

_DRIVE_QUERY_OPERATORS = (
    "contains", "mimeType", "trashed", "starred", "fullText",
    "modifiedTime", "createdTime", "'me'", " in ", "parents", "owners", " = ", "!=",
)


class FileSummary(TypedDict):
    id: str
    name: str
    mime_type: str
    is_folder: bool
    parents: list[str]
    web_view_link: str


def looks_like_drive_id(s: str) -> bool:
    return bool(_LIKELY_BARE_ID.match(s.strip()))


def extract_file_id(url_or_id: str) -> str:
    """Pull a Drive file ID from a URL, or accept a bare ID (>=25 chars)."""
    s = (url_or_id or "").strip()
    if not s:
        raise ValueError("empty file reference")
    m = _FILE_ID_IN_PATH.search(s) or _FILE_ID_IN_QUERY.search(s)
    if m:
        return m.group(1)
    if looks_like_drive_id(s):
        return s
    raise ValueError(
        f"could not extract a Drive file ID from {url_or_id!r}; pass a Drive URL or file ID"
    )


def build_search_query(query: str, only_folders: bool = False) -> str:
    """Wrap a plain string as a name search; pass raw Drive query syntax through. Optionally restrict to folders."""
    if any(op in query for op in _DRIVE_QUERY_OPERATORS):
        base = query
    else:
        safe = query.replace("\\", "\\\\").replace("'", "\\'")
        base = f"name contains '{safe}' and trashed = false"
    if only_folders and "mimeType" not in base:
        base = f"{base} and mimeType = '{FOLDER_MIME}'"
    return base


def plan_move(current_parents: list[str], dest_id: str, keep_existing_parents: bool = False) -> tuple[str, str]:
    """Pure: compute (addParents, removeParents) for a move. Empty removeParents means 'add only'."""
    add = dest_id
    remove = "" if keep_existing_parents else ",".join(current_parents)
    return add, remove


def _shape_file(f: dict) -> FileSummary:
    return {
        "id": f.get("id", ""),
        "name": f.get("name", ""),
        "mime_type": f.get("mimeType", ""),
        "is_folder": f.get("mimeType") == FOLDER_MIME,
        "parents": f.get("parents", []),
        "web_view_link": f.get("webViewLink", ""),
    }


def search(query: str, only_folders: bool = False, max_results: int = 20) -> list[FileSummary]:
    svc = service()
    resp = svc.files().list(
        q=build_search_query(query, only_folders=only_folders),
        pageSize=max(1, min(max_results, 100)),
        fields="files(id,name,mimeType,parents,webViewLink)",
        orderBy="folder,modifiedTime desc",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return [_shape_file(f) for f in resp.get("files", [])]


def resolve_folder_id(dest: str) -> str:
    """Resolve a destination folder given an ID, URL, 'root', or an unambiguous folder name."""
    s = (dest or "").strip()
    if not s:
        raise ValueError("empty destination folder")
    if s.lower() == "root":
        return "root"
    m = _FILE_ID_IN_PATH.search(s) or _FILE_ID_IN_QUERY.search(s)
    if m:
        return m.group(1)
    if looks_like_drive_id(s):
        return s
    # Treat as a folder name — must resolve to exactly one folder.
    folders = search(s, only_folders=True, max_results=20)
    exact = [f for f in folders if f["name"] == s]
    if len(exact) == 1:
        return exact[0]["id"]
    if not exact:
        raise ValueError(
            f"no folder named {s!r} found — create it first or pass a folder ID/URL"
        )
    cands = ", ".join(f"{f['name']} ({f['id']})" for f in exact)
    raise ValueError(f"multiple folders named {s!r}; pass the folder ID/URL instead. Candidates: {cands}")


def create_folder(name: str, parent: str | None = None) -> FileSummary:
    svc = service()
    body: dict = {"name": name, "mimeType": FOLDER_MIME}
    if parent:
        body["parents"] = [resolve_folder_id(parent)]
    f = svc.files().create(
        body=body,
        fields="id,name,mimeType,parents,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return _shape_file(f)


def move(file: str, dest_folder: str, keep_existing_parents: bool = False) -> dict:
    """Move a file or folder into dest_folder. By default removes it from its current parents (true move)."""
    svc = service()
    file_id = extract_file_id(file)
    meta = svc.files().get(
        fileId=file_id,
        fields="id,name,parents,mimeType,webViewLink",
        supportsAllDrives=True,
    ).execute()
    dest_id = resolve_folder_id(dest_folder)
    current_parents = meta.get("parents", [])
    add, remove = plan_move(current_parents, dest_id, keep_existing_parents)

    updated = svc.files().update(
        fileId=file_id,
        addParents=add,
        removeParents=remove,
        fields="id,name,parents,mimeType,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "id": updated.get("id", ""),
        "name": updated.get("name", ""),
        "is_folder": updated.get("mimeType") == FOLDER_MIME,
        "moved_from": current_parents,
        "moved_to": dest_id,
        "parents_now": updated.get("parents", []),
        "web_view_link": updated.get("webViewLink", ""),
    }


def guess_mime_type(filename: str, override: str | None = None) -> str:
    """Pure: pick a MIME type for an upload — explicit override wins, else guess from the name, else octet-stream."""
    if override:
        return override
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def upload_file(
    local_path: str,
    parent: str | None = None,
    name: str | None = None,
    mime_type: str | None = None,
) -> dict:
    """Upload a local file to Drive via a resumable media upload (streams bytes from disk, handles large binaries).

    The file is stored as-is — no Google-format conversion happens, because we never set a Google target
    MIME type in the metadata (only the media's MIME type). So a .xlsx stays a .xlsx, a .zip stays a .zip.

    Args:
        local_path: Path to a local file ('~' expanded).
        parent: Destination folder — ID/URL/'root'/unambiguous folder name. Default: My Drive root.
        name: Drive filename. Default: the local basename.
        mime_type: Override the MIME type. Default: guessed from the name, else application/octet-stream.
    """
    p = Path(local_path).expanduser()
    if not p.exists():
        raise ValueError(f"local file not found: {local_path}")
    if not p.is_file():
        raise ValueError(f"not a regular file: {local_path}")

    svc = service()
    body: dict = {"name": name or p.name}
    if parent:
        body["parents"] = [resolve_folder_id(parent)]
    media = MediaFileUpload(str(p), mimetype=guess_mime_type(p.name, mime_type), resumable=True)
    f = svc.files().create(
        body=body,
        media_body=media,
        fields="id,name,mimeType,parents,size,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "id": f.get("id", ""),
        "name": f.get("name", ""),
        "mime_type": f.get("mimeType", ""),
        "size_bytes": int(f["size"]) if f.get("size") else None,
        "parents": f.get("parents", []),
        "web_view_link": f.get("webViewLink", ""),
        "local_path": str(p),
    }
