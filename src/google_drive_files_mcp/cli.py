"""Command-line interface: setup, Drive file ops (search/mkdir/move/upload), Sheets editing, server runner."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from googleapiclient.errors import HttpError

from . import __version__, client, config, sheets
from .auth import DriveAuthError, authenticate, token_status

SETUP_GUIDE = """\
=== google-drive-files-mcp setup ===

This tool MOVES, UPLOADS, ORGANIZES files and EDITS Google Sheets, so it needs the full Drive scope
(read + write). Before continuing you need an OAuth client JSON from Google Cloud Console.

  1. Open https://console.cloud.google.com/ and sign in.
  2. Create/reuse a project. Enable the Drive API and the Sheets API:
       https://console.cloud.google.com/apis/library/drive.googleapis.com
       https://console.cloud.google.com/apis/library/sheets.googleapis.com
  3. OAuth consent screen:
       - Google Workspace: User type = Internal (no verification needed even for the restricted scope).
       - Personal Gmail: User type = External, add your address as a test user.
  4. APIs & Services -> Credentials -> Create credentials -> OAuth client ID:
       - Application type: Desktop app -> download the JSON.
  5. Move the JSON to:
       {dest}
     (Or set $GDRIVE_FILES_MCP_CREDENTIALS to its path.)

Re-run `google-drive-files-mcp setup` and a browser will open for consent.
Token is cached at:
       {token}
"""


def _emit(fn: Callable[[], object]) -> int:
    """Print fn()'s result as JSON, or a clean error to stderr. Returns a process exit code."""
    try:
        print(json.dumps(fn(), indent=2))
        return 0
    except (DriveAuthError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except HttpError as e:
        print(f"error: Google API error: {e}", file=sys.stderr)
        return 2


def _json_arg(raw: str, what: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"{what} must be valid JSON: {e}") from e


# ----------------------------------------------------------------- setup / status

def cmd_setup(args: argparse.Namespace) -> int:
    config.ensure_config_dir()
    cred = config.credentials_path()
    token = config.token_path()
    if args.import_credentials:
        src = Path(args.import_credentials).expanduser()
        if not src.exists():
            print(f"error: {src} does not exist", file=sys.stderr)
            return 1
        shutil.copy(src, cred)
        try:
            cred.chmod(0o600)
        except OSError:
            pass
        print(f"copied {src} -> {cred}")
    if not cred.exists():
        print(SETUP_GUIDE.format(dest=cred, token=token))
        return 0
    if args.reauth and token.exists():
        token.unlink()
        print(f"removed {token}, will re-authorize")
    print(f"using credentials: {cred}")
    print("opening browser for OAuth consent…")
    try:
        authenticate(allow_browser=True)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"success. token cached at {token}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    print(json.dumps({
        "version": __version__,
        "config_dir": str(config.config_dir()),
        "credentials_path": str(config.credentials_path()),
        "credentials_present": config.credentials_path().exists(),
        "token": token_status(),
        "scopes": config.scopes(),
    }, indent=2))
    return 0


# ----------------------------------------------------------------- drive files

def cmd_search(a):
    return _emit(lambda: client.search(a.query, only_folders=a.folders, max_results=a.max))


def cmd_mkdir(a):
    return _emit(lambda: client.create_folder(a.name, parent=a.parent))


def cmd_move(a):
    return _emit(lambda: client.move(a.file, a.dest, keep_existing_parents=a.keep))


def cmd_upload(a):
    return _emit(lambda: client.upload_file(a.local_path, parent=a.parent, name=a.name, mime_type=a.mime_type))


def cmd_serve(a):
    from .server import main as run_server
    run_server()
    return 0


# ----------------------------------------------------------------- sheets

def _vio(a):
    return "RAW" if getattr(a, "raw", False) else "USER_ENTERED"


def cmd_sheet_info(a):
    return _emit(lambda: sheets.get_info(a.spreadsheet))


def cmd_sheet_read(a):
    return _emit(lambda: sheets.read(a.spreadsheet, a.range, render_option=a.render))


def cmd_sheet_write(a):
    return _emit(lambda: sheets.write(a.spreadsheet, a.range, _json_arg(a.values, "values"), value_input_option=_vio(a)))


def cmd_sheet_append(a):
    return _emit(lambda: sheets.append(a.spreadsheet, a.range, _json_arg(a.values, "values"), value_input_option=_vio(a)))


def cmd_sheet_clear(a):
    return _emit(lambda: sheets.clear(a.spreadsheet, a.range))


def cmd_sheet_batch(a):
    return _emit(lambda: sheets.batch_write(a.spreadsheet, _json_arg(a.updates, "updates"), value_input_option=_vio(a)))


def cmd_sheet_add_tab(a):
    return _emit(lambda: sheets.add_tab(a.spreadsheet, a.title, rows=a.rows, cols=a.cols))


def cmd_sheet_rename_tab(a):
    return _emit(lambda: sheets.rename_tab(a.spreadsheet, a.tab, a.new_title))


def cmd_sheet_delete_tab(a):
    return _emit(lambda: sheets.delete_tab(a.spreadsheet, a.tab))


def cmd_sheet_format(a):
    return _emit(lambda: sheets.format_cells(a.spreadsheet, a.range, number_format=a.number_format,
                                             bold=a.bold, background=a.background))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="google-drive-files-mcp",
        description="MCP server + CLI for Google Drive file management (search, move, upload, folders) and Google Sheets editing.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="one-time OAuth setup (full drive scope)")
    s.add_argument("--import-credentials", metavar="PATH")
    s.add_argument("--reauth", action="store_true")
    s.set_defaults(func=cmd_setup)

    sub.add_parser("status", help="show config + token status").set_defaults(func=cmd_status)

    se = sub.add_parser("search", help="search files/folders")
    se.add_argument("query")
    se.add_argument("--folders", action="store_true", help="only folders")
    se.add_argument("--max", type=int, default=20)
    se.set_defaults(func=cmd_search)

    mk = sub.add_parser("mkdir", help="create a folder")
    mk.add_argument("name")
    mk.add_argument("--parent", default=None, help="parent folder ID/URL/name/root")
    mk.set_defaults(func=cmd_mkdir)

    mv = sub.add_parser("move", help="move a file/folder into a destination folder")
    mv.add_argument("file")
    mv.add_argument("dest")
    mv.add_argument("--keep", action="store_true", help="add to dest without removing from current folder(s)")
    mv.set_defaults(func=cmd_move)

    up = sub.add_parser("upload", help="upload a local file into a Drive folder")
    up.add_argument("local_path")
    up.add_argument("--parent", default=None, help="destination folder ID/URL/name/root")
    up.add_argument("--name", default=None, help="Drive filename (default: local basename)")
    up.add_argument("--mime-type", default=None, dest="mime_type", help="override MIME type")
    up.set_defaults(func=cmd_upload)

    # --- sheets ---
    si = sub.add_parser("sheet-info", help="list a spreadsheet's tabs and sizes")
    si.add_argument("spreadsheet")
    si.set_defaults(func=cmd_sheet_info)

    sr = sub.add_parser("sheet-read", help="read an A1 range")
    sr.add_argument("spreadsheet")
    sr.add_argument("range")
    sr.add_argument("--render", default="FORMATTED_VALUE",
                    choices=["FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"])
    sr.set_defaults(func=cmd_sheet_read)

    sw = sub.add_parser("sheet-write", help="overwrite a range (values = JSON 2D array)")
    sw.add_argument("spreadsheet")
    sw.add_argument("range")
    sw.add_argument("values", help="JSON 2D array, e.g. '[[1],[2],[3]]'")
    sw.add_argument("--raw", action="store_true", help="write literally (no number/formula parsing)")
    sw.set_defaults(func=cmd_sheet_write)

    sa = sub.add_parser("sheet-append", help="append rows (values = JSON 2D array)")
    sa.add_argument("spreadsheet")
    sa.add_argument("range")
    sa.add_argument("values", help="JSON 2D array")
    sa.add_argument("--raw", action="store_true")
    sa.set_defaults(func=cmd_sheet_append)

    sc = sub.add_parser("sheet-clear", help="clear values in a range")
    sc.add_argument("spreadsheet")
    sc.add_argument("range")
    sc.set_defaults(func=cmd_sheet_clear)

    sb = sub.add_parser("sheet-batch", help="write many ranges (updates = JSON [{range,values}])")
    sb.add_argument("spreadsheet")
    sb.add_argument("updates", help='JSON, e.g. \'[{"range":"A1","values":[[1]]}]\'')
    sb.add_argument("--raw", action="store_true")
    sb.set_defaults(func=cmd_sheet_batch)

    at = sub.add_parser("sheet-add-tab", help="add a tab")
    at.add_argument("spreadsheet")
    at.add_argument("title")
    at.add_argument("--rows", type=int, default=1000)
    at.add_argument("--cols", type=int, default=26)
    at.set_defaults(func=cmd_sheet_add_tab)

    rt = sub.add_parser("sheet-rename-tab", help="rename a tab")
    rt.add_argument("spreadsheet")
    rt.add_argument("tab", help="current tab title or numeric sheetId")
    rt.add_argument("new_title")
    rt.set_defaults(func=cmd_sheet_rename_tab)

    dt = sub.add_parser("sheet-delete-tab", help="delete a tab (destructive)")
    dt.add_argument("spreadsheet")
    dt.add_argument("tab", help="tab title or numeric sheetId")
    dt.set_defaults(func=cmd_sheet_delete_tab)

    sf = sub.add_parser("sheet-format", help="format a range (number pattern / bold / background)")
    sf.add_argument("spreadsheet")
    sf.add_argument("range")
    sf.add_argument("--number-format", dest="number_format", default=None, help="e.g. '#,##0.00', '0.00%%'")
    sf.add_argument("--bold", action="store_true", default=None)
    sf.add_argument("--background", default=None, help="#RRGGBB")
    sf.set_defaults(func=cmd_sheet_format)

    sub.add_parser("serve", help="run the MCP server (stdio)").set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
