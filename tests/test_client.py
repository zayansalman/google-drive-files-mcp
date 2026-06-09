"""Unit tests for pure functions in client.py — no network, no auth."""
import pytest

from google_drive_files_mcp.client import (
    FOLDER_MIME,
    build_search_query,
    extract_file_id,
    looks_like_drive_id,
    plan_move,
)

DOC_ID = "1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUvWxYz12345"  # 41 chars


class TestLooksLikeDriveId:
    def test_long_id(self):
        assert looks_like_drive_id(DOC_ID) is True

    def test_short_name_rejected(self):
        assert looks_like_drive_id("Reports") is False

    def test_medium_name_rejected(self):
        # 16 chars, looks word-ish but below the 25-char ID threshold
        assert looks_like_drive_id("ProjectAlpha2026") is False

    def test_name_with_space_rejected(self):
        assert looks_like_drive_id("My Long Folder Name Here Yes") is False


class TestExtractFileId:
    def test_docs_url(self):
        assert extract_file_id(f"https://docs.google.com/document/d/{DOC_ID}/edit") == DOC_ID

    def test_drive_file_url(self):
        assert extract_file_id(f"https://drive.google.com/file/d/{DOC_ID}/view") == DOC_ID

    def test_open_id_url(self):
        assert extract_file_id(f"https://drive.google.com/open?id={DOC_ID}") == DOC_ID

    def test_bare_long_id(self):
        assert extract_file_id(DOC_ID) == DOC_ID

    def test_short_name_raises(self):
        with pytest.raises(ValueError):
            extract_file_id("Reports")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            extract_file_id("")


class TestBuildSearchQuery:
    def test_plain_wrapped(self):
        assert build_search_query("Q3") == "name contains 'Q3' and trashed = false"

    def test_only_folders_appends_mime(self):
        q = build_search_query("Reports", only_folders=True)
        assert "name contains 'Reports'" in q
        assert FOLDER_MIME in q

    def test_raw_passthrough(self):
        q = "mimeType = 'application/vnd.google-apps.folder'"
        assert build_search_query(q) == q

    def test_escapes_quote(self):
        assert build_search_query("Zayan's") == "name contains 'Zayan\\'s' and trashed = false"


class TestPlanMove:
    def test_true_move_removes_current_parents(self):
        add, remove = plan_move(["parentA", "parentB"], "destX")
        assert add == "destX"
        assert remove == "parentA,parentB"

    def test_keep_existing_parents_adds_only(self):
        add, remove = plan_move(["parentA"], "destX", keep_existing_parents=True)
        assert add == "destX"
        assert remove == ""

    def test_no_current_parents(self):
        add, remove = plan_move([], "destX")
        assert add == "destX"
        assert remove == ""
