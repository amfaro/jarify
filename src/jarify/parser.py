"""SQL parsing utilities built on sqlglot."""

from __future__ import annotations

import functools
import re
import typing

import sqlglot
import sqlglot.expressions as _exp
from sqlglot.dialects.duckdb import DuckDB as _DuckDB
from sqlglot.errors import ParseError
from sqlglot.expressions import Expression

DUCKDB_DIALECT = "duckdb"

# ---------------------------------------------------------------------------
# Custom DuckDB dialect — preserve bare NUMERIC/DECIMAL without injecting
# default precision/scale into the AST.
# ---------------------------------------------------------------------------
# sqlglot's DuckDB parser registers a TYPE_CONVERTERS handler for DECIMAL that
# calls build_default_decimal_type(precision=18, scale=3).  This fires for any
# bare NUMERIC or DECIMAL type (no user-supplied params) and injects (18, 3)
# into the AST, causing jarify to regenerate `decimal(18, 3)` when the
# original SQL only said `numeric` or `decimal`.  We remove that converter so
# bare types stay bare and round-trip cleanly.


class _JarifyDuckDBParser(_DuckDB.Parser):
    TYPE_CONVERTERS: typing.ClassVar = {
        k: v for k, v in _DuckDB.Parser.TYPE_CONVERTERS.items() if k != _exp.DType.DECIMAL
    }


class _JarifyDuckDB(_DuckDB):
    Parser = _JarifyDuckDBParser


_JARIFY_DIALECT: type[_DuckDB] = _JarifyDuckDB

# ---------------------------------------------------------------------------
# Rust format-string placeholder handling
# ---------------------------------------------------------------------------
# SQL files used as Rust format-string templates may contain placeholders like
# {where_clause} that are substituted at runtime.  These are not valid SQL, so
# we mask them before handing off to sqlglot, then restore them afterward.
#
# Pattern: {identifier} where the identifier starts with a letter/underscore
# and has no colon (which would indicate a DuckDB struct key, e.g. {key: v}).
#
# Two masking strategies are applied depending on line context:
#   • Line-level placeholder (whole line is just the placeholder):
#       → SQL block comment: /* __J_RFP_N__ */
#       A block comment is valid anywhere between SQL clauses.
#   • Inline placeholder (placeholder shares a line with other SQL tokens):
#       → Valid SQL identifier: __jrfpN__
#       An identifier is valid anywhere a name or expression is expected.

_RUST_FMT_RE = re.compile(r"\{[A-Za-z_]\w*\}")
_RUST_FMT_LINE_RE = re.compile(r"^\s*\{[A-Za-z_]\w*\}\s*$")
_AS_TRAILING_RE = re.compile(r"\bAS$", re.IGNORECASE)


def _mask_rust_fmt_placeholders(sql: str) -> tuple[str, dict[str, str]]:
    """Replace Rust format placeholders with syntactically valid SQL tokens.

    Used by the linter so placeholder tokens do not trigger parse errors.
    Returns ``(masked_sql, {marker: original_placeholder})``.
    The mapping is empty when no placeholders are present.

    Two strategies by line context:
    - Whole-line placeholder → SQL block comment (valid between clauses)
    - Inline placeholder    → dummy identifier  (valid as name/expression)
    """
    mapping: dict[str, str] = {}
    seq = [0]

    def _next_marker(placeholder: str, *, inline: bool) -> str:
        n = seq[0]
        seq[0] += 1
        if inline:
            base = f"__jrfp{n}__"
            # Pad to original length so string-literal widths are preserved
            # during AS-alignment computation (see _compute_as_align_width).
            extra = max(0, len(placeholder) - len(base))
            marker = base + "_" * extra
        else:
            marker = f"/* __J_RFP_{n}__ */"
        mapping[marker] = placeholder
        return marker

    result_lines: list[str] = []
    for line in sql.splitlines(keepends=True):
        if _RUST_FMT_LINE_RE.match(line):
            m = _RUST_FMT_RE.search(line)
            assert m is not None
            result_lines.append(line.replace(m.group(0), _next_marker(m.group(0), inline=False)))
        else:
            result_lines.append(_RUST_FMT_RE.sub(lambda m: _next_marker(m.group(0), inline=True), line))

    return "".join(result_lines), mapping


def _unmask_rust_fmt_placeholders(sql: str, mapping: dict[str, str]) -> str:
    """Restore Rust format placeholders from their masked tokens."""
    for marker, original in mapping.items():
        sql = sql.replace(marker, original)
    return sql


def _extract_ctas_body_placeholders(sql: str) -> tuple[str, dict[str, str]]:
    """Replace whole-line placeholders that serve as a CTAS body with dummy markers.

    A placeholder is a CTAS body when it immediately follows a line ending with
    the keyword ``AS`` (case-insensitive).  The dummy body ``SELECT * FROM
    __J_CTAS_BODY_N__`` lets sqlglot parse a complete, valid CTAS so neither
    the ``AS`` keyword nor surrounding structure is dropped.

    Returns ``(modified_sql, {marker: original_placeholder_line})``.  When no
    such pattern exists the SQL is returned unchanged with an empty mapping.
    """
    ctas_body_map: dict[str, str] = {}
    counter = 0
    lines = sql.splitlines(keepends=True)
    result: list[str] = []

    for i, line in enumerate(lines):
        if _RUST_FMT_LINE_RE.match(line):
            # Find the previous non-blank line to check for a trailing AS.
            prev_content = ""
            for j in range(i - 1, -1, -1):
                stripped = lines[j].strip()
                if stripped:
                    prev_content = stripped
                    break
            if _AS_TRAILING_RE.search(prev_content):
                marker = f"__J_CTAS_BODY_{counter}__"
                ctas_body_map[marker] = line.rstrip("\r\n")
                result.append(f"SELECT * FROM {marker}\n")
                counter += 1
                continue
        result.append(line)

    return "".join(result), ctas_body_map


def _restore_ctas_body_placeholders(sql: str, ctas_body_map: dict[str, str]) -> str:
    """Restore CTAS body placeholders from their dummy markers.

    Replaces the entire formatted line that contains a CTAS body marker with
    the original placeholder text.
    """
    if not ctas_body_map:
        return sql
    lines = sql.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        replaced = False
        for marker, original in ctas_body_map.items():
            if marker in line:
                result.append(original + "\n")
                replaced = True
                break
        if not replaced:
            result.append(line)
    return "".join(result)


def _extract_line_rust_fmt_placeholders(
    sql: str,
) -> tuple[str, list[tuple[list[str], list[str], str | None]]]:
    """Strip whole-line Rust format placeholder lines from ``sql``.

    Used by the formatter so the stripped SQL can be formatted normally, then
    the placeholders can be re-inserted at the correct positions afterward.

    Returns ``(stripped_sql, [(group, trailing_blanks, anchor), ...])``.
    *group* is a list of one or more consecutive placeholder lines (their full
    text, leading whitespace preserved).  *trailing_blanks* is a list of blank
    lines that immediately follow the group — they are consumed here so the
    formatter does not strip them as leading whitespace, and re-emitted by
    ``_reinsert_line_rust_fmt_placeholders``.  *anchor* is the stripped text
    of the first non-blank, non-placeholder line after the group; it is
    ``None`` when no such line exists.  Grouping consecutive placeholders
    together ensures they are re-inserted in their original order before the
    same anchor occurrence.
    """
    lines = sql.splitlines(keepends=True)
    result_lines: list[str] = []
    insertions: list[tuple[list[str], list[str], str | None]] = []

    i = 0
    while i < len(lines):
        if _RUST_FMT_LINE_RE.match(lines[i]):
            # Collect all adjacent placeholder lines into one group so they
            # are re-inserted together (preserving relative order) before a
            # single anchor occurrence.
            group: list[str] = []
            while i < len(lines) and _RUST_FMT_LINE_RE.match(lines[i]):
                m = _RUST_FMT_RE.search(lines[i])
                assert m is not None
                group.append(lines[i].rstrip("\r\n"))
                i += 1
            # Consume blank lines that immediately follow the placeholder
            # group.  Without this, the formatter receives SQL beginning with
            # blank lines and strips them, making fmt non-idempotent on files
            # that separate a placeholder block from the first SQL statement
            # with a blank line.
            trailing_blanks: list[str] = []
            while i < len(lines) and not lines[i].strip():
                trailing_blanks.append(lines[i])
                i += 1
            anchor: str | None = None
            for j in range(i, len(lines)):
                candidate = lines[j].strip()
                if candidate and not _RUST_FMT_LINE_RE.match(lines[j]):
                    anchor = candidate
                    break
            insertions.append((group, trailing_blanks, anchor))
        else:
            result_lines.append(lines[i])
            i += 1

    return "".join(result_lines), insertions


def _reinsert_line_rust_fmt_placeholders(sql: str, insertions: list[tuple[list[str], list[str], str | None]]) -> str:
    """Re-insert whole-line placeholder groups into formatted SQL.

    Each group is inserted immediately before the first occurrence of its
    anchor line (compared after stripping whitespace), preserving all lines in
    the group in their original order.  Trailing blank lines recorded during
    extraction are emitted after the group and before the anchor.  Groups with
    no anchor are appended at the end.
    """
    if not insertions:
        return sql

    lines = sql.splitlines(keepends=True)
    # Work through groups in order; pop the first matching anchor each time so
    # that two groups with the same anchor text land before different
    # occurrences of that anchor in the formatted SQL.
    pending = list(insertions)
    result: list[str] = []

    for line in lines:
        stripped = line.strip()
        for idx, (group, trailing_blanks, anchor) in enumerate(pending):
            if anchor is not None and stripped == anchor:
                for placeholder in group:
                    result.append(placeholder + "\n")
                result.extend(trailing_blanks)
                pending.pop(idx)
                break
        result.append(line)

    # Append any remaining (no-anchor) groups before the trailing newline
    for group, trailing_blanks, _ in pending:
        for placeholder in group:
            result.append(placeholder + "\n")
        result.extend(trailing_blanks)

    return "".join(result)


# ---------------------------------------------------------------------------
# ifnull preservation
# ---------------------------------------------------------------------------
# sqlglot's DuckDB dialect maps IFNULL to exp.Coalesce at parse time, losing
# the original function name.  We mask it with a sentinel before parsing so
# sqlglot treats it as an unknown (Anonymous) function and preserves the name,
# then restore it after generation.

# Sentinel must be the same length as "ifnull" (6 chars) so that AS-column
# alignment computed during generation is not thrown off before the unmask.
_IFNULL_SENTINEL = "_ifnl_"
_IFNULL_RE = re.compile(r"\bifnull\b", re.IGNORECASE)


def _mask_ifnull(sql: str) -> str:
    """Replace ifnull with a sentinel so sqlglot doesn't normalize it to coalesce."""
    return _IFNULL_RE.sub(_IFNULL_SENTINEL, sql)


def _unmask_ifnull(sql: str) -> str:
    """Restore ifnull from its sentinel."""
    return sql.replace(_IFNULL_SENTINEL, "ifnull")


# ---------------------------------------------------------------------------
# Reserved-keyword type-cast pre-processor
# ---------------------------------------------------------------------------
# DuckDB allows user-defined types whose names are SQL reserved words, e.g.
#   COALESCE(x, []::filter[])
# sqlglot fails to parse these because it sees ``filter`` as a keyword token,
# not a type name.  Quoting them — ``::"filter"[]`` — makes sqlglot parse
# correctly; the generator then emits the unquoted ``::filter[]`` form again.


@functools.lru_cache(maxsize=1)
def _reserved_cast_re() -> re.Pattern[str]:
    """Return a compiled regex that matches ``::keyword`` cast type names
    where the keyword is a DuckDB reserved word that sqlglot cannot parse as
    an unquoted type.  Result is cached so the build only happens once per
    process.
    """
    from sqlglot.dialects.duckdb import DuckDB
    from sqlglot.tokens import TokenType

    tokenizer = DuckDB.Tokenizer()
    type_tokens = DuckDB.Parser.TYPE_TOKENS

    reserved: list[str] = []
    for kw in DuckDB.Tokenizer.KEYWORDS:
        word = kw.strip().lower()
        if not word.isalpha():
            continue
        toks = tokenizer.tokenize(word)
        if not toks:
            continue
        tt = toks[0].token_type
        # VAR = plain identifier; TYPE_TOKENS = sqlglot-recognised type tokens.
        # Both are safe as unquoted type names; everything else needs quoting.
        if tt != TokenType.VAR and tt not in type_tokens:
            reserved.append(word)

    words_pat = "|".join(re.escape(w) for w in sorted(reserved, key=len, reverse=True))
    # Match ::keyword or ::keyword[] but NOT ::keyword_something (word boundary via (?!\w))
    return re.compile(rf"::({words_pat})(\[\])?(?!\w)", re.IGNORECASE)


def _quote_reserved_cast_types(sql: str) -> str:
    """Quote reserved keywords used as cast type names so sqlglot can parse them.

    ``[]::filter[]`` → ``[]::"filter"[]``

    The generator round-trips this back to the unquoted ``::filter[]`` form.
    """

    def _replacer(m: re.Match[str]) -> str:
        return f'::"{m.group(1)}"{m.group(2) or ""}'

    return _reserved_cast_re().sub(_replacer, sql)


def _read_dialect(dialect: str) -> type[_DuckDB] | str:
    """Return the parser dialect to use for *dialect*.

    For the DuckDB dialect we substitute our custom subclass that preserves
    bare NUMERIC/DECIMAL types without injecting default precision/scale.
    All other dialects are passed through unchanged.
    """
    return _JARIFY_DIALECT if dialect == DUCKDB_DIALECT else dialect


def parse_sql(sql: str, dialect: str = DUCKDB_DIALECT) -> list[Expression]:
    """Parse a SQL string into a list of sqlglot expression trees.

    Raises ParseError if the SQL is invalid.  Applies a pre-processing step
    to quote DuckDB reserved keywords used as cast type names (e.g.
    ``::filter[]``) so sqlglot can handle them.
    """
    preprocessed = _quote_reserved_cast_types(sql)
    return sqlglot.parse(preprocessed, read=_read_dialect(dialect), error_level=sqlglot.ErrorLevel.RAISE)


def parse_sql_lenient(sql: str, dialect: str = DUCKDB_DIALECT) -> tuple[list[Expression], list[ParseError]]:
    """Parse SQL leniently, collecting errors instead of raising."""
    preprocessed = _quote_reserved_cast_types(sql)
    read = _read_dialect(dialect)
    errors: list[ParseError] = []
    try:
        trees = sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.RAISE)
    except ParseError:
        # Fall back to lenient parsing so we still get partial trees.
        # Use IGNORE (not WARN) to suppress sqlglot's side-effect stderr prints;
        # errors are re-captured via the RAISE pass below.
        trees = sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.IGNORE)
        # Re-parse to capture the actual errors
        try:
            sqlglot.parse(preprocessed, read=read, error_level=sqlglot.ErrorLevel.RAISE)
        except ParseError as e:
            errors.append(e)
    return trees, errors
