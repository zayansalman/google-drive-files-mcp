"""Unit tests for pure functions in sheets.py — no network, no auth."""
import pytest

from google_drive_files_mcp.sheets import (
    col_to_index,
    hex_to_rgb,
    parse_a1,
    spreadsheet_id,
)

SS_ID = "1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUvWxYz12345"  # 41 chars


class TestColToIndex:
    def test_a(self):
        assert col_to_index("A") == 0

    def test_z(self):
        assert col_to_index("Z") == 25

    def test_aa(self):
        assert col_to_index("AA") == 26

    def test_ab(self):
        assert col_to_index("AB") == 27

    def test_lowercase(self):
        assert col_to_index("c") == 2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            col_to_index("")


class TestHexToRgb:
    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == {"red": 1.0, "green": 1.0, "blue": 1.0}

    def test_black_no_hash(self):
        assert hex_to_rgb("000000") == {"red": 0.0, "green": 0.0, "blue": 0.0}

    def test_red(self):
        c = hex_to_rgb("#FF0000")
        assert c["red"] == 1.0 and c["green"] == 0.0 and c["blue"] == 0.0

    def test_bad_length_raises(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#FFF")

    def test_non_hex_raises(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#GGGGGG")


class TestParseA1:
    def test_single_cell(self):
        r = parse_a1("A1")
        assert r == {"sheet": None, "start_row": 0, "end_row": 1, "start_col": 0, "end_col": 1}

    def test_range(self):
        r = parse_a1("A1:C5")
        assert (r["start_row"], r["end_row"], r["start_col"], r["end_col"]) == (0, 5, 0, 3)

    def test_with_sheet(self):
        r = parse_a1("Sheet1!B2:D4")
        assert r["sheet"] == "Sheet1"
        assert (r["start_row"], r["end_row"], r["start_col"], r["end_col"]) == (1, 4, 1, 4)

    def test_quoted_sheet(self):
        r = parse_a1("'My Sheet'!A1:A1")
        assert r["sheet"] == "My Sheet"

    def test_whole_columns(self):
        r = parse_a1("A:C")
        assert r["start_col"] == 0 and r["end_col"] == 3
        assert r["start_row"] is None and r["end_row"] is None

    def test_whole_rows(self):
        r = parse_a1("2:5")
        assert r["start_row"] == 1 and r["end_row"] == 5
        assert r["start_col"] is None and r["end_col"] is None

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_a1("")


class TestSpreadsheetId:
    def test_url(self):
        assert spreadsheet_id(f"https://docs.google.com/spreadsheets/d/{SS_ID}/edit#gid=0") == SS_ID

    def test_bare_id(self):
        assert spreadsheet_id(SS_ID) == SS_ID
