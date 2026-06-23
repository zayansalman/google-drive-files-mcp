"""OAuth flow + token management."""
from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from . import config


class DriveAuthError(RuntimeError):
    """Raised when authentication can't proceed without user intervention."""


def _load_token() -> Credentials | None:
    path = config.token_path()
    if not path.exists():
        return None
    return Credentials.from_authorized_user_file(str(path), config.scopes())


def _save_token(creds: Credentials) -> None:
    path = config.token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    try:
        path.chmod(0o600)
    except OSError:
        pass


def authenticate(allow_browser: bool = False) -> Credentials:
    """Return valid Credentials. Refresh if expired. Open browser only if allow_browser=True."""
    creds = _load_token()
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds

    if not allow_browser:
        raise DriveAuthError(
            f"No valid Google token at {config.token_path()}. "
            "Run `google-drive-files-mcp setup` from a terminal to authorize."
        )

    cred_path = config.credentials_path()
    if not cred_path.exists():
        raise DriveAuthError(
            f"OAuth client secret not found at {cred_path}. "
            "Either set $GDRIVE_FILES_MCP_CREDENTIALS, or run `google-drive-files-mcp setup --help`."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), config.scopes())
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def service() -> Resource:
    """Build an authenticated Drive API service client. Will not open a browser."""
    return build("drive", "v3", credentials=authenticate(allow_browser=False))


def sheets_service() -> Resource:
    """Build an authenticated Google Sheets API client. Will not open a browser.

    The full `drive` scope already authorizes the Sheets API, so no extra consent is needed —
    but the Sheets API must be enabled on the OAuth client's Google Cloud project.
    """
    return build("sheets", "v4", credentials=authenticate(allow_browser=False))


def docs_service() -> Resource:
    """Build an authenticated Google Docs API client. Will not open a browser.

    The full `drive` scope already authorizes the Docs API, so no extra consent is needed —
    but the Docs API must be enabled on the OAuth client's Google Cloud project.
    """
    return build("docs", "v1", credentials=authenticate(allow_browser=False))


def token_status() -> dict:
    creds = _load_token()
    if creds is None:
        return {"present": False, "path": str(config.token_path())}
    return {
        "present": True,
        "path": str(config.token_path()),
        "valid": creds.valid,
        "expired": creds.expired,
        "has_refresh_token": bool(creds.refresh_token),
        "scopes": list(creds.scopes or []),
    }
