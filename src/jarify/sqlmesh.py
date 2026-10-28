"""SQLMesh-aware segmentation and runtime token masking helpers.

These helpers intentionally do not parse SQLMesh.  They preserve SQLMesh-only
wrappers, top-level macro statements and opaque Jinja blocks verbatim, then make
inline runtime tokens look like ordinary SQL identifiers so sqlglot can
format/lint the surrounding SQL.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SqlMeshSegment:
    """A byte-preserved SQLMesh document segment."""

    kind: Literal["sql", "opaque"]
    text: str


_SQLMESH_AT_IDENTIFIER_RE = re.compile(r"@[A-Za-z_]\w*\b")
_MACRO_CALL_RE = re.compile(r"@[A-Za-z_]\w*\s*\(")
_LINE_END_RE = re.compile(r"[\r\n]")
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
            # As long as the original wherever it's three characters or more,
            # so the widths jarify aligns AS and table aliases by are the
            # widths of the unmasked SQL. The `_` on both sides keeps one
            # marker from occurring inside another.
            marker = f"_{seq}_"
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
        for kind, text in _split_macro_statements("".join(sql_buf)):
            if kind == "opaque":
                _append_segment(segments, "opaque", text)
            else:
                _append_sql_lines(segments, text)
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


def _append_sql_lines(segments: list[SqlMeshSegment], sql: str) -> None:
    """Append *sql* as a SQL segment, keeping its edge blank lines opaque."""
    lines = sql.splitlines(keepends=True)
    first_sql = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_sql is None:
        _append_segment(segments, "opaque", sql)
        return
    last_sql = max(idx for idx, line in enumerate(lines) if line.strip())
    _append_segment(segments, "opaque", "".join(lines[:first_sql]))
    _append_segment(segments, "sql", "".join(lines[first_sql : last_sql + 1]))
    _append_segment(segments, "opaque", "".join(lines[last_sql + 1 :]))


@dataclass(frozen=True)
class _Statement:
    """Offsets of one top-level statement in a SQL stretch."""

    start: int  # end of the previous statement, so leading comments are included
    code_start: int  # first character that is not whitespace or a comment
    end: int  # just past the statement's ";", or the end of the text
    is_macro: bool


def _split_macro_statements(sql: str) -> list[tuple[Literal["sql", "opaque"], str]]:
    """Split *sql* into SQL pieces and opaque top-level macro statements.

    A macro statement is a statement whose only code is a SQLMesh macro call
    followed by ``;``, such as ``@DEF(x, 1);`` or ``@ensure_sql_macro('n');``.
    SQLMesh runs these as pre/post-statements; they are kept exactly as
    written.  Each opaque piece starts on the line after the previous
    statement (or at the start of *sql*), so the comments and blank lines
    above the macro statement stay with it, and ends after the line holding
    its ``;``.  When no statement follows, it runs to the end of *sql* so
    trailing comments stay too.

    Macro statements that share a line with other SQL are left in the SQL
    piece and formatted as ordinary statements.
    """
    if "@" not in sql:
        return [("sql", sql)]
    statements = _split_statements(sql)
    pieces: list[tuple[Literal["sql", "opaque"], str]] = []
    pos = 0
    for start, end in _macro_statement_spans(sql, statements):
        if start > pos:
            pieces.append(("sql", sql[pos:start]))
        pieces.append(("opaque", sql[start:end]))
        pos = end
    if pos < len(sql):
        pieces.append(("sql", sql[pos:]))
    return pieces


def _split_statements(sql: str) -> list[_Statement]:
    statements: list[_Statement] = []
    start = 0
    while True:
        code_start = _skip_leading_space_and_comments(sql, start)
        if code_start >= len(sql):
            return statements
        end = _find_statement_end(sql, code_start)
        statements.append(_Statement(start, code_start, end, _is_macro_statement(sql, code_start, end)))
        start = end


def _find_statement_end(sql: str, pos: int) -> int:
    for i in _code_positions(sql, pos):
        if sql[i] == ";":
            return i + 1
    return len(sql)


def _is_macro_statement(sql: str, code_start: int, end: int) -> bool:
    match = _MACRO_CALL_RE.match(sql, code_start)
    if not match:
        return False
    call_end = _find_closing_paren(sql, match.end() - 1)
    if call_end is None:
        return False
    semicolon = _skip_leading_space_and_comments(sql, call_end)
    return semicolon == end - 1 and sql[semicolon] == ";"


def _macro_statement_spans(sql: str, statements: list[_Statement]) -> list[tuple[int, int]]:
    """Return the ``(start, end)`` offsets of the opaque macro-statement pieces.

    Macro statements chained on one line form a single run.  A run is opaque
    only when a line break separates it from the statements around it.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(statements):
        if not statements[i].is_macro:
            i += 1
            continue
        first = i
        while (
            i + 1 < len(statements)
            and statements[i + 1].is_macro
            and _line_break_end(sql, statements[i + 1].start, statements[i + 1].code_start) is None
        ):
            i += 1
        last = i
        i += 1

        start = 0 if first == 0 else _line_break_end(sql, statements[first].start, statements[first].code_start)
        if last == len(statements) - 1:
            end: int | None = len(sql)
        else:
            end = _line_break_end(sql, statements[last].end, statements[last + 1].code_start)
        if start is not None and end is not None:
            spans.append((start, end))
    return spans


def _line_break_end(sql: str, start: int, stop: int) -> int | None:
    """Return the offset just past the first line break in ``sql[start:stop]``.

    Line breaks inside block comments do not count.  Returns None when the
    range has no line break.
    """
    for i in _code_positions(sql, start):
        if i >= stop:
            return None
        if sql[i] == "\n":
            return i + 1
    return None


def _code_positions(sql: str, start: int) -> Iterator[int]:
    """Yield offsets from *start* on that lie outside string literals and comments.

    The line break that ends a ``--`` comment is yielded.
    """
    i = start
    while i < len(sql):
        if sql[i] in "'\"":
            i = _skip_quoted(sql, i)
        elif sql.startswith("--", i):
            line_end = _LINE_END_RE.search(sql, i + 2)
            i = line_end.start() if line_end else len(sql)
        elif sql.startswith("/*", i):
            close = sql.find("*/", i + 2)
            i = close + 2 if close != -1 else len(sql)
        else:
            yield i
            i += 1


def _skip_quoted(sql: str, pos: int) -> int:
    """Return the offset just past the quoted string or identifier at *pos*."""
    quote = sql[pos]
    i = pos + 1
    while True:
        close = sql.find(quote, i)
        if close == -1:
            return len(sql)
        if sql.startswith(quote, close + 1):
            i = close + 2
            continue
        return close + 1


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
    return _find_closing_paren(sql, match.end() - 1)


def _find_closing_paren(sql: str, open_paren: int) -> int | None:
    """Return the offset just past the ``)`` that closes the ``(`` at *open_paren*."""
    depth = 0
    for i in _code_positions(sql, open_paren):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return None
