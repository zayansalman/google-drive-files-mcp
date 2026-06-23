"""Unit tests for pure functions in docs.py — no network, no auth."""
import pytest

from google_drive_files_mcp.docs import (
    build_text_and_index_map,
    delete_range,
    document_id,
    find_anchor_index,
    insert_text,
    iter_text_runs,
)

DOC_ID = "1A2b3C4d5E6f7G8h9I0jKlMnOpQrStUvWxYz12345"


def _para(start, text):
    """Build a Docs paragraph structural element with one textRun."""
    return {"paragraph": {"elements": [
        {"startIndex": start, "endIndex": start + len(text), "textRun": {"content": text}}
    ]}}


class TestDocumentId:
    def test_url(self):
        assert document_id(f"https://docs.google.com/document/d/{DOC_ID}/edit") == DOC_ID

    def test_bare_id(self):
        assert document_id(DOC_ID) == DOC_ID


class TestIterTextRuns:
    def test_paragraphs(self):
        content = [_para(1, "Hello "), _para(7, "World\n")]
        runs = list(iter_text_runs(content))
        assert [r["text"] for r in runs] == ["Hello ", "World\n"]
        assert runs[0]["start_index"] == 1 and runs[1]["start_index"] == 7
        assert all(r["in_table"] is False for r in runs)

    def test_table_cells_carry_row_col(self):
        table = {"table": {"tableRows": [
            {"tableCells": [
                {"content": [_para(10, "A1")]},
                {"content": [_para(14, "B1")]},
            ]},
        ]}}
        runs = list(iter_text_runs([table]))
        assert [(r["text"], r["row"], r["col"], r["in_table"]) for r in runs] == [
            ("A1", 0, 0, True), ("B1", 0, 1, True),
        ]


class TestBuildTextAndIndexMap:
    def test_concatenation_and_map(self):
        runs = [
            {"start_index": 1, "text": "ab"},
            {"start_index": 5, "text": "cd"},   # a gap in doc indices (e.g. across structural elements)
        ]
        full, idx = build_text_and_index_map(runs)
        assert full == "abcd"
        assert idx == [1, 2, 5, 6]


class TestFindAnchorIndex:
    def setup_method(self):
        runs = [{"start_index": 1, "text": "Hello World"}]  # doc indices 1..11
        self.full, self.idx = build_text_and_index_map(runs)

    def test_after(self):
        # "Hello" occupies doc indices 1..5; insert-after = 6
        assert find_anchor_index(self.full, self.idx, "Hello", "after") == 6

    def test_before(self):
        # "World" starts at doc index 7
        assert find_anchor_index(self.full, self.idx, "World", "before") == 7

    def test_missing_raises(self):
        with pytest.raises(ValueError):
            find_anchor_index(self.full, self.idx, "Nope", "after")

    def test_bad_position_raises(self):
        with pytest.raises(ValueError):
            find_anchor_index(self.full, self.idx, "Hello", "sideways")

    def test_empty_anchor_raises(self):
        with pytest.raises(ValueError):
            find_anchor_index(self.full, self.idx, "", "after")


class TestInsertValidation:
    # these guards trigger before any API call, so no network is needed
    def test_both_anchors_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            insert_text(DOC_ID, "x", after_text="a", before_text="b")

    def test_none_provided_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            insert_text(DOC_ID, "x")

    def test_index_and_anchor_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            insert_text(DOC_ID, "x", index=5, after_text="a")


class TestDeleteRangeValidation:
    def test_start_below_one_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            delete_range(DOC_ID, 0, 5)

    def test_start_ge_end_raises(self):
        with pytest.raises(ValueError, match="< end_index"):
            delete_range(DOC_ID, 5, 5)
