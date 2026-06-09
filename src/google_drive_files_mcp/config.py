"""Configuration: paths and defaults driven by env vars with XDG-ish fallbacks.

NOTE: the default scope is the FULL drive scope, because moving an existing arbitrary
file (files.update with addParents/removeParents) cannot be done with any narrower scope.
"""
import os
from pathlib import Path

ENV_CREDENTIALS = "GDRIVE_FILES_MCP_CREDENTIALS"
ENV_TOKEN = "GDRIVE_FILES_MCP_TOKEN"
ENV_SCOPES = "GDRIVE_FILES_MCP_SCOPES"  # comma-separated; default is full drive (write)

DEFAULT_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def config_dir() -> Path:
    return _xdg_config_home() / "google-drive-files-mcp"


def credentials_path() -> Path:
    override = os.environ.get(ENV_CREDENTIALS)
    if override:
        return Path(override).expanduser()
    return config_dir() / "credentials.json"


def token_path() -> Path:
    override = os.environ.get(ENV_TOKEN)
    if override:
        return Path(override).expanduser()
    return config_dir() / "token.json"


def scopes() -> list[str]:
    override = os.environ.get(ENV_SCOPES)
    if override:
        return [s.strip() for s in override.split(",") if s.strip()]
    return list(DEFAULT_SCOPES)


def ensure_config_dir() -> Path:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d
