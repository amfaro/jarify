"""SQLMesh-aware segmentation and runtime token masking helpers.

These helpers intentionally do not parse SQLMesh.  They preserve SQLMesh-only
wrappers and opaque Jinja blocks verbatim, then make inline runtime tokens look
like ordinary SQL identifiers so sqlglot can format/lint the surrounding SQL.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SqlMeshSegment:
    """A byte-preserved SQLMesh document segment."""

    kind: Literal["sql", "opaque"]
    text: str


_SQLMESH_AT_IDENTIFIER_RE = re.compile(r"@[A-Za-z_]\w*\b")
_HEADER_RE = re.compile(r"\b(MODEL|AUDIT)\s*\(", re.IGNORECASE)
_LEADING_HEADER_RE = re.compile(r"(?:MODEL|AUDIT)\s*\(", re.IGNORECASE)
_SQLMESH_MARKER_RE = re.compile(
    r"\b(?:ON_VIRTUAL_UPDATE_BEGIN|ON_VIRTUAL_UPDATE_END|JINJA_STATEMENT_BEGIN|JINJA_END)\b"
)
_JINJA_EXPR_RE = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_WHOLE_LINE_JINJA_EXPR_RE = re.compile(r"^\s*\{\{.*\}\}\s*;?\s*$", re.DOTALL)
_WHOLE_LINE_JINJA_STMT_RE = re.compile(r"^\s*\{%-?\s*(\w+)", re.IGNORECASE)
_JINJA_BLOCK_START = frozenset({"if", "for", "macro", "filter", "set", "block", "call", "with"})
_JINJA_BLOCK_END = frozenset({"endif", "endfor", "endmacro", "endfilter", "endset", "endblock", "endcall", "endwith"})


def looks_like_sqlmesh(sql: str) -> bool:
    """Return True when *sql* contains SQLMesh wrapper/template markers."""
    leading = _skip_leading_space_and_comments(sql, 0)
    if _LEADING_HEADER_RE.match(sql, leading):
        return True
    if _SQLMESH_MARKER_RE.search(sql):
        return True
    if "{{" in sql or "{%" in sql:
        return True
    return _contains_sqlmesh_at_identifier(sql)


def split_sqlmesh_segments(sql: str) -> list[SqlMeshSegment]:
    """Split a SQLMesh document into formatable SQL and opaque segments."""
    if not sql:
        return [SqlMeshSegment("sql", sql)]

    segments: list[SqlMeshSegment] = []
    pos = 0

    while True:
        header_start = _skip_leading_space_and_comments(sql, pos)
        match = _LEADING_HEADER_RE.match(sql, header_start)
        if not match:
            break
        header_end = _find_balanced_call_end(sql, match.start())
        if header_end is None:
            break
        opaque_end = _consume_optional_semicolon_and_blank_lines(sql, header_end)
        _append_segment(segments, "opaque", sql[pos:opaque_end])
        pos = opaque_end

    _append_line_segments(segments, sql[pos:])
    return segments or [SqlMeshSegment("sql", sql)]


def mask_sqlmesh_runtime_tokens(sql: str) -> tuple[str, dict[str, str]]:
    """Mask inline SQLMesh/Jinja runtime tokens with valid SQL identifiers."""
    source_sql = sql
    mapping: dict[str, str] = {}
    used_markers: set[str] = set()
    seq = 0

    def next_marker(original: str) -> str:
        nonlocal seq
        while True:
            marker = f"__jsm{seq}__"
            seq += 1
            if len(marker) < len(original):
                marker += "_" * (len(original) - len(marker))
            if marker in source_sql or marker in used_markers:
                continue
            used_markers.add(marker)
            mapping[marker] = original
            return marker

    sql = _JINJA_EXPR_RE.sub(lambda m: next_marker(m.group(0)), sql)
    if "@" not in sql:
        return sql, mapping

    return _replace_sqlmesh_at_identifiers(sql, next_marker), mapping


def unmask_sqlmesh_runtime_tokens(sql: str, mapping: dict[str, str]) -> str:
    """Restore SQLMesh/Jinja runtime tokens from *mapping*."""
    for marker, original in mapping.items():
        sql = sql.replace(marker, original)
    return sql


def _contains_sqlmesh_at_identifier(sql: str) -> bool:
    return _replace_sqlmesh_at_identifiers(sql, lambda _original: "") != sql


def _replace_sqlmesh_at_identifiers(sql: str, replacement_for: Callable[[str], str]) -> str:
    parts: list[str] = []
    i = 0
    state = "code"
    changed = False

    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if state == "code":
            if ch == "'":
                state = "single"
                parts.append(ch)
                i += 1
                continue
            if ch == '"':
                state = "double"
                parts.append(ch)
                i += 1
                continue
            if ch == "-" and nxt == "-":
                state = "line_comment"
                parts.append(ch + nxt)
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                parts.append(ch + nxt)
                i += 2
                continue
            match = _SQLMESH_AT_IDENTIFIER_RE.match(sql, i)
            if match:
                parts.append(replacement_for(match.group(0)))
                i = match.end()
                changed = True
                continue
            parts.append(ch)
            i += 1
            continue

        parts.append(ch)
        i += 1
        if state == "single":
            if ch == "'" and nxt == "'":
                parts.append(nxt)
                i += 1
            elif ch == "'":
                state = "code"
        elif state == "double":
            if ch == '"' and nxt == '"':
                parts.append(nxt)
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "line_comment" and ch in "\r\n":
            state = "code"
        elif state == "block_comment" and ch == "*" and nxt == "/":
            parts.append(nxt)
            i += 1
            state = "code"

    return "".join(parts) if changed else sql


def _append_segment(segments: list[SqlMeshSegment], kind: Literal["sql", "opaque"], text: str) -> None:
    if not text:
        return
    if segments and segments[-1].kind == kind:
        segments[-1] = SqlMeshSegment(kind, segments[-1].text + text)
    else:
        segments.append(SqlMeshSegment(kind, text))


def _append_line_segments(segments: list[SqlMeshSegment], sql: str) -> None:
    lines = sql.splitlines(keepends=True)
    sql_buf: list[str] = []
    i = 0

    def flush_sql() -> None:
        nonlocal sql_buf
        if not sql_buf:
            return
        first_sql = next((idx for idx, sql_line in enumerate(sql_buf) if sql_line.strip()), None)
        if first_sql is None:
            _append_segment(segments, "opaque", "".join(sql_buf))
            sql_buf = []
            return
        last_sql = max(idx for idx, sql_line in enumerate(sql_buf) if sql_line.strip())
        _append_segment(segments, "opaque", "".join(sql_buf[:first_sql]))
        _append_segment(segments, "sql", "".join(sql_buf[first_sql : last_sql + 1]))
        _append_segment(segments, "opaque", "".join(sql_buf[last_sql + 1 :]))
        sql_buf = []

    while i < len(lines):
        line = lines[i]
        if "JINJA_STATEMENT_BEGIN" in line:
            flush_sql()
            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                end = "JINJA_END" in lines[i]
                i += 1
                if end:
                    break
            _append_segment(segments, "opaque", "".join(block))
            continue

        if "ON_VIRTUAL_UPDATE_BEGIN" in line or "ON_VIRTUAL_UPDATE_END" in line:
            flush_sql()
            _append_segment(segments, "opaque", line)
            i += 1
            continue

        if _WHOLE_LINE_JINJA_EXPR_RE.match(line):
            flush_sql()
            _append_segment(segments, "opaque", line)
            i += 1
            continue

        jinja_match = _WHOLE_LINE_JINJA_STMT_RE.match(line)
        if jinja_match:
            tag = jinja_match.group(1).lower()
            flush_sql()
            block, i = _collect_jinja_statement_block(lines, i, tag)
            _append_segment(segments, "opaque", "".join(block))
            continue

        sql_buf.append(line)
        i += 1

    flush_sql()


def _collect_jinja_statement_block(lines: list[str], start: int, first_tag: str) -> tuple[list[str], int]:
    block: list[str] = []
    depth = 0
    i = start
    is_block = first_tag in _JINJA_BLOCK_START

    while i < len(lines):
        line = lines[i]
        block.append(line)
        match = _WHOLE_LINE_JINJA_STMT_RE.match(line)
        if match:
            tag = match.group(1).lower()
            if tag in _JINJA_BLOCK_START:
                depth += 1
            elif tag in _JINJA_BLOCK_END:
                depth = max(0, depth - 1)
        i += 1
        if not is_block or depth == 0:
            break

    return block, i


def _skip_leading_space_and_comments(sql: str, pos: int) -> int:
    i = pos
    while i < len(sql):
        if sql[i].isspace():
            i += 1
            continue
        if sql.startswith("--", i):
            newline = sql.find("\n", i + 2)
            if newline == -1:
                return len(sql)
            i = newline + 1
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end == -1:
                return len(sql)
            i = end + 2
            continue
        break
    return i


def _consume_optional_semicolon_and_blank_lines(sql: str, pos: int) -> int:
    i = pos
    while i < len(sql) and sql[i] in " \t":
        i += 1
    if i < len(sql) and sql[i] == ";":
        i += 1
    if i < len(sql) and sql[i] == "\r":
        i += 1
    if i < len(sql) and sql[i] == "\n":
        i += 1
    while True:
        line_end = sql.find("\n", i)
        if line_end == -1:
            line = sql[i:]
            if line.strip():
                return i
            return len(sql)
        line = sql[i : line_end + 1]
        if line.strip():
            return i
        i = line_end + 1


def _find_balanced_call_end(sql: str, call_start: int) -> int | None:
    match = _HEADER_RE.match(sql, call_start)
    if not match:
        return None

    depth = 0
    i = match.end() - 1
    state = "code"
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        if state == "code":
            if ch == "'":
                state = "single"
            elif ch == '"':
                state = "double"
            elif ch == "-" and nxt == "-":
                state = "line_comment"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block_comment"
                i += 1
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        elif state == "single":
            if ch == "'" and nxt == "'":
                i += 1
            elif ch == "'":
                state = "code"
        elif state == "double":
            if ch == '"' and nxt == '"':
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "line_comment" and ch in "\r\n":
            state = "code"
        elif state == "block_comment" and ch == "*" and nxt == "/":
            state = "code"
            i += 1
        i += 1

    return None
