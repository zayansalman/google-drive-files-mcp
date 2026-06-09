"""Command-line interface: setup wizard, search/mkdir/move helpers, server runner."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__, client, config
from .auth import DriveAuthError, authenticate, token_status

SETUP_GUIDE = """\
=== google-drive-files-mcp setup ===

This tool MOVES and ORGANIZES files in your Google Drive, so it needs the full
Drive scope (read + write). Before continuing you need an OAuth client JSON from
Google Cloud Console. If you already have one, skip to step 4.

  1. Open https://console.cloud.google.com/ and sign in.
  2. Create/reuse a project. Enable the Drive API at
     https://console.cloud.google.com/apis/library/drive.googleapis.com
  3. OAuth consent screen:
       - Google Workspace: User type = Internal (no verification needed even for
         the restricted full-drive scope).
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


def cmd_search(args: argparse.Namespace) -> int:
    try:
        print(json.dumps(
            client.search(args.query, only_folders=args.folders, max_results=args.max), indent=2
        ))
        return 0
    except DriveAuthError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def cmd_mkdir(args: argparse.Namespace) -> int:
    try:
        print(json.dumps(client.create_folder(args.name, parent=args.parent), indent=2))
        return 0
    except DriveAuthError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def cmd_move(args: argparse.Namespace) -> int:
    try:
        print(json.dumps(
            client.move(args.file, args.dest, keep_existing_parents=args.keep), indent=2
        ))
        return 0
    except DriveAuthError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import main as run_server
    run_server()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="google-drive-files-mcp",
        description="MCP server + CLI for moving/organizing Google Drive files (move, create folders).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="one-time OAuth setup (full drive scope)")
    s.add_argument("--import-credentials", metavar="PATH")
    s.add_argument("--reauth", action="store_true")
    s.set_defaults(func=cmd_setup)

    st = sub.add_parser("status", help="show config + token status")
    st.set_defaults(func=cmd_status)

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
    mv.add_argument("file", help="file/folder URL or ID")
    mv.add_argument("dest", help="destination folder ID/URL/name/root")
    mv.add_argument("--keep", action="store_true",
                    help="add to dest without removing from current folder(s)")
    mv.set_defaults(func=cmd_move)

    sv = sub.add_parser("serve", help="run the MCP server (stdio)")
    sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
