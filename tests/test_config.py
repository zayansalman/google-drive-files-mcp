"""Unit tests for config.py — env var resolution and defaults."""
from pathlib import Path

import pytest

from google_drive_files_mcp import config


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for var in (config.ENV_CREDENTIALS, config.ENV_TOKEN, config.ENV_SCOPES):
        monkeypatch.delenv(var, raising=False)


def test_credentials_default():
    assert config.credentials_path() == config.config_dir() / "credentials.json"


def test_token_default():
    assert config.token_path() == config.config_dir() / "token.json"


def test_scopes_default_is_full_drive():
    assert config.scopes() == ["https://www.googleapis.com/auth/drive"]


def test_scopes_override(monkeypatch):
    monkeypatch.setenv(config.ENV_SCOPES, "a, b,c")
    assert config.scopes() == ["a", "b", "c"]


def test_credentials_override(monkeypatch, tmp_path):
    custom = tmp_path / "c.json"
    monkeypatch.setenv(config.ENV_CREDENTIALS, str(custom))
    assert config.credentials_path() == custom


def test_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.config_dir() == tmp_path / "google-drive-files-mcp"


def test_tilde_expansion(monkeypatch):
    monkeypatch.setenv(config.ENV_TOKEN, "~/t.json")
    assert config.token_path() == Path.home() / "t.json"
