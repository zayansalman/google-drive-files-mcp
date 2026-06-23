"""Google Docs surgical in-place editing via documents.batchUpdate.

Every edit is range-scoped — replacing a phrase, inserting at one index, or deleting one range —
so all other content keeps its native formatting untouched. Read first (with indices) to target edits.
"""
from __future__ import annotations

from typing import TypedDict

from .auth import docs_service
from .client import extract_file_id  # reuses /d/<id> URL + bare-id extraction (works for Docs URLs)


def document_id(document: str) -> str:
    """Accept a Docs URL or a bare document ID."""
    return extract_file_id(document)


class TextRun(TypedDict):
    start_index: int
    end_index: int
    text: str
    in_table: bool
    row: int | None
    col: int | None


# ---------------------------------------------------------------- pure helpers

def iter_text_runs(content: list, in_table: bool = False, row=None, col=None):
    """Recursively yield textRun segments (with document indices) from a Docs body 'content' list."""
    for el in content or []:
        if "paragraph" in el:
            for pe in el["paragraph"].get("elements", []):
                tr = pe.get("textRun")
                if tr is not None and "content" in tr:
                    yield {
                        "start_index": pe.get("startIndex", 0),
                        "end_index": pe.get("endIndex", 0),
                        "text": tr["content"],
                        "in_table": in_table,
                        "row": row,
                        "col": col,
                    }
        elif "table" in el:
            for r, trow in enumerate(el["table"].get("tableRows", [])):
                for c, cell in enumerate(trow.get("tableCells", [])):
                    yield from iter_text_runs(cell.get("content") or [], in_table=True, row=r, col=c)


def build_text_and_index_map(runs: list[dict]) -> tuple[str, list[int]]:
    """Concatenate run text and build a char->document-index map (idx_map[k] = doc index of k-th char)."""
    chars: list[str] = []
    idx_map: list[int] = []
    for run in runs:
        start = run["start_index"]
        for i, ch in enumerate(run["text"]):
            chars.append(ch)
            idx_map.append(start + i)
    return "".join(chars), idx_map


def find_anchor_index(full_text: str, idx_map: list[int], anchor: str, position: str = "after") -> int:
    """Return the document index just after (or before) the first occurrence of `anchor`."""
    if not anchor:
        raise ValueError("anchor text is empty")
    pos = full_text.find(anchor)
    if pos < 0:
        raise ValueError(f"anchor text not found in document: {anchor!r}")
    if position == "before":
        return idx_map[pos]
    if position == "after":
        return idx_map[pos + len(anchor) - 1] + 1
    raise ValueError(f"position must be 'before' or 'after', got {position!r}")


# ---------------------------------------------------------------- inspect

def _load(document: str):
    svc = docs_service()
    did = document_id(document)
    doc = svc.documents().get(documentId=did).execute()
    return svc, did, doc


def get_info(document: str) -> dict:
    _svc, did, doc = _load(document)
    content = doc.get("body", {}).get("content", [])
    paragraphs = sum(1 for el in content if "paragraph" in el)
    tables = sum(1 for el in content if "table" in el)
    end_index = content[-1].get("endIndex", 1) if content else 1
    return {"document_id": did, "title": doc.get("title", ""),
            "paragraphs": paragraphs, "tables": tables, "end_index": end_index}


def read(document: str) -> dict:
    """Read the document's text with per-segment document indices (so edits can target exact spots)."""
    _svc, did, doc = _load(document)
    content = doc.get("body", {}).get("content", [])
    runs = list(iter_text_runs(content))
    full_text, _idx = build_text_and_index_map(runs)
    segments = [{
        "text": r["text"],
        "start_index": r["start_index"],
        "end_index": r["end_index"],
        "in_table": r["in_table"],
        "row": r["row"],
        "col": r["col"],
    } for r in runs]
    end_index = content[-1].get("endIndex", 1) if content else 1
    return {"document_id": did, "title": doc.get("title", ""),
            "text": full_text, "segments": segments, "end_index": end_index}


# ---------------------------------------------------------------- surgical edits

def replace_text(document: str, find: str, replace: str, match_case: bool = False) -> dict:
    """Replace every occurrence of `find` with `replace`. Surrounding content/formatting is untouched."""
    if not find:
        raise ValueError("`find` text is empty")
    svc, did, _doc = _load(document)
    resp = svc.documents().batchUpdate(documentId=did, body={"requests": [
        {"replaceAllText": {"containsText": {"text": find, "matchCase": match_case}, "replaceText": replace}}
    ]}).execute()
    changed = resp.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    return {"find": find, "replace": replace, "occurrences_changed": changed}


def insert_text(document: str, text: str, index: int | None = None,
                after_text: str | None = None, before_text: str | None = None) -> dict:
    """Insert `text` at a document index, or relative to an anchor phrase (after_text / before_text).

    Anchors use the FIRST occurrence of the phrase. To insert a new paragraph, include a newline in `text`.
    """
    if sum(x is not None for x in (index, after_text, before_text)) != 1:
        raise ValueError("provide exactly one of: index, after_text, or before_text")
    svc, did, doc = _load(document)
    if index is None:
        runs = list(iter_text_runs(doc.get("body", {}).get("content", [])))
        full_text, idx_map = build_text_and_index_map(runs)
        anchor, position = (after_text, "after") if after_text is not None else (before_text, "before")
        index = find_anchor_index(full_text, idx_map, anchor, position)
    if index < 1:
        raise ValueError(f"insert index must be >= 1 (Docs is 1-based), got {index}")
    svc.documents().batchUpdate(documentId=did, body={"requests": [
        {"insertText": {"location": {"index": index}, "text": text}}
    ]}).execute()
    return {"inserted_at_index": index, "chars_inserted": len(text)}


def delete_range(document: str, start_index: int, end_index: int) -> dict:
    """Delete one content range [start_index, end_index)."""
    if start_index < 1:
        raise ValueError(f"start_index must be >= 1 (Docs is 1-based), got {start_index}")
    if start_index >= end_index:
        raise ValueError("start_index must be < end_index")
    svc, did, _doc = _load(document)
    svc.documents().batchUpdate(documentId=did, body={"requests": [
        {"deleteContentRange": {"range": {"startIndex": start_index, "endIndex": end_index}}}
    ]}).execute()
    return {"deleted_range": [start_index, end_index]}


def append_text(document: str, text: str) -> dict:
    """Append `text` at the end of the document body."""
    svc, did, doc = _load(document)
    content = doc.get("body", {}).get("content", [])
    end_index = content[-1].get("endIndex", 2) if content else 2
    index = end_index - 1  # the last insertable position (before the body's final newline)
    svc.documents().batchUpdate(documentId=did, body={"requests": [
        {"insertText": {"location": {"index": index}, "text": text}}
    ]}).execute()
    return {"inserted_at_index": index, "chars_inserted": len(text)}
