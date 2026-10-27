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
from sqlglot.tokens import TokenType

DUCKDB_DIALECT = "duckdb"

# ---------------------------------------------------------------------------
# Custom DuckDB dialect - preserve bare NUMERIC/DECIMAL without injecting
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
    # sqlglot treats bare TRANSFORM(...) as DuckDB's list-transform function and
    # rewrites it to LIST_TRANSFORM(...). DuckDB documents LIST_TRANSFORM and its
    # explicit aliases, but not a bare TRANSFORM alias; projects may define their
    # own `transform` macro. Remove the special-case parser entry so bare
    # TRANSFORM(...) round-trips as an anonymous function call.
    FUNCTIONS: typing.ClassVar = {k: v for k, v in _DuckDB.Parser.FUNCTIONS.items() if k != "TRANSFORM"}
    UNARY_PARSERS: typing.ClassVar = {
        **_DuckDB.Parser.UNARY_PARSERS,
        TokenType.NOT: lambda self: self._parse_not(),
    }

    # sqlglot drops the comments on the keywords below: it reads a keyword's
    # comments only until it reads the next token, and for these it never
    # does.  The overrides keep them.

    def _parse_not(self) -> _exp.Not:
        # Comments written before NOT go on the Not node, like a comment
        # before any other condition; those written after it are kept for
        # the generator to write after NOT.
        before, after = self._split_comments(self._index - 1)
        not_ = self.expression(_exp.Not(this=self._parse_equality()))
        if before:
            not_.add_comments(before, prepend=True)
        _set_keyword_comments(not_, "NOT", after)
        return not_

    def _parse_qualify(self) -> _exp.Qualify | None:
        # As for WHERE and HAVING, the comments on QUALIFY go on the clause.
        if not self._match(TokenType.QUALIFY):
            return None
        comments = self._prev_comments
        return self.expression(_exp.Qualify(this=self._parse_disjunction()), comments=comments)

    def _parse_join(
        self,
        skip_join_token: bool = False,
        parse_bracket: bool = False,
        alias_tokens: typing.Collection[TokenType] | None = None,
    ) -> _exp.Join | None:
        start = self._index
        join = super()._parse_join(
            skip_join_token=skip_join_token, parse_bracket=parse_bracket, alias_tokens=alias_tokens
        )
        # The comments on ON or USING go on the join, as the comments on
        # WHERE go on the WHERE clause.
        if join is not None and (join.args.get("on") or join.args.get("using")):
            keywords = _top_level_tokens(self._tokens[start : self._index], {TokenType.ON, TokenType.USING})
            if keywords and keywords[-1].comments:
                join.add_comments(keywords[-1].comments)
        return join

    def _parse_case(self) -> _exp.Expr | None:
        start = self._index
        case = super()._parse_case()
        if not isinstance(case, _exp.Case):
            return case
        # Each WHEN / THEN keeps its comments on its branch, ELSE on the CASE.
        keywords = _top_level_tokens(
            self._tokens[start : self._index], {TokenType.WHEN, TokenType.THEN, TokenType.ELSE}
        )
        branches = case.args.get("ifs") or []
        for keyword, token_type in (("WHEN", TokenType.WHEN), ("THEN", TokenType.THEN)):
            tokens = [token for token in keywords if token.token_type == token_type]
            if len(tokens) == len(branches):
                for branch, token in zip(branches, tokens, strict=True):
                    _set_keyword_comments(branch, keyword, token.comments)
        else_tokens = [token for token in keywords if token.token_type == TokenType.ELSE]
        if else_tokens:
            _set_keyword_comments(case, "ELSE", else_tokens[-1].comments)
        return case

    def _parse_if(self) -> _exp.Expr | None:
        # `if(…)` drops the comments on IF, such as one on the line above the
        # call, and those on its closing paren, such as one written between
        # the call and its AS.  Other calls keep them.
        comments = self._prev_comments
        result = super()._parse_if()
        if result is not None:
            if comments:
                result.add_comments(comments, prepend=True)
            if self._prev.token_type == TokenType.R_PAREN:
                self._add_comments(result)
        return result

    def _parse_window(self, this: _exp.Expr | None, alias: bool = False) -> _exp.Expr | None:
        result = super()._parse_window(this, alias=alias)
        # An aggregate's `FILTER (…)` drops the comments on its closing paren.
        if isinstance(result, _exp.Filter) and self._prev.token_type == TokenType.R_PAREN:
            self._add_comments(result)
        return result

    def parse_set_operation(self, this: _exp.Expr | None, consume_pipe: bool = False) -> _exp.Expr | None:
        start = self._index
        operation = super().parse_set_operation(this, consume_pipe=consume_pipe)
        # sqlglot keeps the comments on UNION, EXCEPT or INTERSECT, but drops
        # those on the words after it, such as ALL or BY NAME.
        if isinstance(operation, _exp.SetOperation):
            tokens = self._tokens[start : self._index]
            keyword = next((i for i, token in enumerate(tokens) if token.token_type in self.SET_OPERATIONS), None)
            for token in tokens[keyword + 1 :] if keyword is not None else []:
                if token.text.upper() not in _SET_OPERATION_MODIFIERS:
                    break
                operation.add_comments(token.comments)
        return operation

    def _parse_subquery(self, this: _exp.Expr | None, parse_alias: bool = True) -> _exp.Subquery | None:
        # A subquery in FROM or JOIN loses the comments on its closing paren
        # when an alias follows.  Those written on their own line before the
        # paren are kept to end the body; those after it go on the subquery.
        closing = bool(self._prev_comments) and self._prev.token_type == TokenType.R_PAREN
        before, after = self._split_comments(self._index - 1) if closing else ([], [])
        if closing:
            self._prev_comments = []
        subquery = super()._parse_subquery(this, parse_alias=parse_alias)
        if closing and subquery is not None:
            _set_keyword_comments(subquery, ")", before)
            if after:
                subquery.add_comments(after)
        return subquery

    def _split_comments(self, index: int) -> tuple[list[str], list[str]]:
        """Split the comments on token *index* into those written before it and those after it.

        The tokenizer gives a token the comments that start on the lines
        between it and the previous token, and those that start on its own
        line after it.
        """
        token = self._tokens[index]
        gap_start = self._tokens[index - 1].end + 1 if index > 0 else 0
        gap = self.sql[gap_start : token.start]
        position = before = 0
        for comment in token.comments:
            for text in (f"--{comment}", f"/*{comment}*/"):
                found = gap.find(text, position)
                if found != -1:
                    position = found + len(text)
                    before += 1
                    break
            else:
                break
        return token.comments[:before], token.comments[before:]

    def _parse_select_query(self, *args: typing.Any, **kwargs: typing.Any) -> _exp.Expr | None:
        # The FROM token of a FROM-first query (`FROM t`, `FROM t SELECT a`)
        # holds the comments written above the query.  sqlglot hands them to
        # the From clause, then drops that clause when it builds the query as
        # `SELECT * FROM t`, deleting the comments; after `FROM t SELECT a` it
        # keeps them on the From clause, which generates after the SELECT list.
        # Put them on the query instead, where a comment above `SELECT` goes.
        from_token = self._curr if self._curr and self._curr.token_type == TokenType.FROM else None
        comments = list(from_token.comments) if from_token else []
        query = super()._parse_select_query(*args, **kwargs)
        if not comments:
            return query

        select = query
        while isinstance(select, _exp.SetOperation):
            select = select.this
        if isinstance(select, _exp.Select):
            from_ = select.args.get("from_")
            if from_ is not None and from_.comments == comments:
                from_.pop_comments()
            select.add_comments(comments, prepend=True)
        return query

    def _parse_cte(self) -> _exp.CTE | _exp.FunctionSpecification | None:
        start = self._index
        cte = super()._parse_cte()
        if not isinstance(cte, _exp.CTE):
            return cte

        # sqlglot keeps the comments on a CTE's AS but drops those between AS
        # and the body's opening paren (`_a AS -- note` survives, `_a AS
        # MATERIALIZED -- note` and an own-line comment before `(` don't).
        # Attach them to the CTE, marked so the generator writes them after AS.
        comments = _comments_before_cte_body(self._tokens[start : self._index])
        if comments:
            cte.add_comments(comments)
            cte.meta[CTE_COMMENTS_AFTER_AS] = comments

        # The CTE takes the comments of the `)` that closes its body, unless it
        # already took comments from its AS.  Then sqlglot leaves them to the
        # next node it builds: the WITH clause, which writes them above the
        # statement, or nothing when a comma follows, which deletes them.
        if self._prev_comments and self._prev.token_type == TokenType.R_PAREN:
            cte.add_comments(self._prev_comments)
            self._prev_comments = []
        return cte


# Meta key on a CTE node: comments written between its AS and the body's "(".
CTE_COMMENTS_AFTER_AS = "jarify_comments_after_as"

# Meta key for comments on a keyword that sqlglot drops, which the generator
# writes at that keyword: {keyword: comments}.  On a Not node, "NOT" holds
# those written after NOT; on a CASE branch (an If node), "WHEN" and "THEN";
# on a Case node, "ELSE"; on a Subquery, ")" holds those written on their own
# line before its closing paren.  They are not in the node's comments, which
# the generator writes after the node.
KEYWORD_COMMENTS = "jarify_keyword_comments"


def keyword_comments(node: _exp.Expr, keyword: str) -> list[str]:
    """Return the comments the parser kept for *keyword* on *node*."""
    return (node.meta_get(KEYWORD_COMMENTS) or {}).get(keyword, [])


def all_keyword_comments(node: _exp.Expr) -> list[str]:
    """Return the comments the parser kept for all keywords of *node*."""
    return [comment for comments in (node.meta_get(KEYWORD_COMMENTS) or {}).values() for comment in comments]


# Words that can follow UNION, EXCEPT or INTERSECT before the next query.
_SET_OPERATION_MODIFIERS = frozenset({"ALL", "DISTINCT", "BY", "NAME", "STRICT", "CORRESPONDING"})


def _set_keyword_comments(node: _exp.Expr, keyword: str, comments: list[str]) -> None:
    comments = [comment for comment in comments if comment.strip()]
    if comments:
        node.meta.setdefault(KEYWORD_COMMENTS, {})[keyword] = comments


def _top_level_tokens(tokens: list[typing.Any], types: set[TokenType]) -> list[typing.Any]:
    """Return the tokens of *types* in *tokens* that are outside parens and nested CASEs."""
    found = []
    depth = 0
    for token in tokens:
        if token.token_type in (TokenType.L_PAREN, TokenType.CASE):
            depth += 1
        elif token.token_type in (TokenType.R_PAREN, TokenType.END):
            depth -= 1
        elif depth == 0 and token.token_type in types:
            found.append(token)
    return found


def _comments_before_cte_body(tokens: list[typing.Any]) -> list[str]:
    """Return the comments on the tokens after a CTE's AS, up to the body's opening paren."""
    as_index = next((i for i, token in enumerate(tokens) if token.token_type == TokenType.ALIAS), None)
    if as_index is None:
        return []
    comments: list[str] = []
    for token in tokens[as_index + 1 :]:
        comments.extend(token.comments)
        if token.token_type == TokenType.L_PAREN:
            break
    return comments


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
) -> tuple[str, list[tuple[list[str], list[str], str | None, str | None]]]:
    """Strip whole-line Rust format placeholder lines from ``sql``.

    Used by the formatter so the stripped SQL can be formatted normally, then
    the placeholders can be re-inserted at the correct positions afterward.

    Returns ``(stripped_sql, [(group, trailing_blanks, anchor, prev_anchor), ...])``.
    *group* is a list of one or more consecutive placeholder lines (their full
    text, leading whitespace preserved).  *trailing_blanks* is a list of blank
    lines that immediately follow the group — they are consumed here so the
    formatter does not strip them as leading whitespace, and re-emitted by
    ``_reinsert_line_rust_fmt_placeholders``.  *anchor* is the stripped text
    of the first non-blank, non-placeholder line after the group; it is
    ``None`` when no such line exists.  *prev_anchor* is the stripped text of
    the last non-blank, non-placeholder line before the group; it is ``None``
    when no such line exists.  When *anchor* text is not unique in the
    formatted SQL (e.g. a bare ``)``) *prev_anchor* disambiguates which
    occurrence to use.  Grouping consecutive placeholders together ensures they
    are re-inserted in their original order before the same anchor occurrence.
    """
    lines = sql.splitlines(keepends=True)
    result_lines: list[str] = []
    insertions: list[tuple[list[str], list[str], str | None, str | None]] = []

    i = 0
    while i < len(lines):
        if _RUST_FMT_LINE_RE.match(lines[i]):
            # Capture the last non-blank, non-placeholder line before the group
            # so re-insertion can disambiguate when the same anchor text appears
            # multiple times in the formatted SQL (e.g. bare ")" after every CTE).
            prev_anchor: str | None = None
            for j in range(len(result_lines) - 1, -1, -1):
                candidate = result_lines[j].strip()
                if candidate and not _RUST_FMT_LINE_RE.match(result_lines[j]):
                    prev_anchor = candidate
                    break
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
            insertions.append((group, trailing_blanks, anchor, prev_anchor))
        else:
            result_lines.append(lines[i])
            i += 1

    return "".join(result_lines), insertions


def _reinsert_line_rust_fmt_placeholders(
    sql: str,
    insertions: list[tuple[list[str], list[str], str | None, str | None]],
) -> str:
    """Re-insert whole-line placeholder groups into formatted SQL.

    Each group is inserted immediately before the first occurrence of its
    anchor line (compared after stripping whitespace), preserving all lines in
    the group in their original order.  Trailing blank lines recorded during
    extraction are emitted after the group and before the anchor.  Groups with
    no anchor are appended at the end.

    When a group has a *prev_anchor* (the last non-blank line before the
    placeholder in the original SQL), an anchor-line match is only accepted
    when the most recently seen non-blank line in the output also matches
    *prev_anchor*.  This disambiguates generic anchor text such as a bare
    ``)``) that appears after every CTE block.
    """
    if not insertions:
        return sql

    lines = sql.splitlines(keepends=True)
    # Work through groups in order; pop the first matching anchor each time so
    # that two groups with the same anchor text land before different
    # occurrences of that anchor in the formatted SQL.
    pending = list(insertions)
    result: list[str] = []
    last_non_blank: str | None = None

    for line in lines:
        stripped = line.strip()
        for idx, (group, trailing_blanks, anchor, prev_anchor) in enumerate(pending):
            if anchor is not None and stripped == anchor:
                # When prev_anchor is set, only accept this occurrence of
                # anchor if the preceding non-blank output line matches it.
                # This prevents a placeholder from landing in an earlier CTE
                # that happens to close with the same token (e.g. ")").
                if prev_anchor is not None and last_non_blank != prev_anchor:
                    continue
                for placeholder in group:
                    result.append(placeholder + "\n")
                result.extend(trailing_blanks)
                pending.pop(idx)
                break
        if stripped:
            last_non_blank = stripped
        result.append(line)

    # Append any remaining (no-anchor) groups before the trailing newline
    for group, trailing_blanks, _, __ in pending:
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
# numeric preservation
# ---------------------------------------------------------------------------
# sqlglot's DuckDB dialect normalises NUMERIC to DType.DECIMAL at parse time,
# losing the original keyword.  We mask it with a same-length sentinel so the
# original spelling is preserved through the format round-trip.
#
# Sentinel is 7 chars (same as "numeric") so type-column alignment in CREATE
# TABLE is not disturbed before the unmask.
_NUMERIC_SENTINEL = "_numer_"
_NUMERIC_RE = re.compile(r"\bnumeric\b", re.IGNORECASE)


def _mask_numeric(sql: str) -> str:
    """Replace numeric with a sentinel so sqlglot doesn't normalise it to decimal."""
    return _NUMERIC_RE.sub(_NUMERIC_SENTINEL, sql)


def _unmask_numeric(sql: str) -> str:
    """Restore numeric from its sentinel."""
    return sql.replace(_NUMERIC_SENTINEL, "numeric")


# ---------------------------------------------------------------------------
# Reserved-keyword type-cast pre-processor
# ---------------------------------------------------------------------------
# DuckDB allows user-defined types whose names are SQL reserved words, e.g.
#   COALESCE(x, []::filter[])
# sqlglot fails to parse these because it sees ``filter`` as a keyword token,
# not a type name.  Quoting them - ``::"filter"[]`` - makes sqlglot parse
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
    trees = sqlglot.parse(preprocessed, read=_read_dialect(dialect), error_level=sqlglot.ErrorLevel.RAISE)
    return _wrap_nested_joins(_hoist_from_table_joins(trees))


# Set in a query's meta when its joins were moved off a FROM-first query's
# table, so the generator keeps writing it FROM-first.
FROM_FIRST_JOINS_KEY = "jarify_from_first_joins"


def _hoist_from_table_joins(trees: list[Expression]) -> list[Expression]:
    """Move joins that sqlglot attached to a query's FROM table onto the query.

    In a FROM-first query (``FROM t p JOIN d dd ON …``) sqlglot puts the joins
    in the FROM table's ``joins`` arg instead of the query's, where the
    generator renders them. Rendering the table and its alias alone then
    dropped every join. Both placements mean the same query, so the joins are
    moved to the query, ahead of any it already has, and the query is marked
    with ``FROM_FIRST_JOINS_KEY``.
    """
    for tree in trees:
        if tree is None:
            continue
        for select in tree.find_all(_exp.Select):
            from_ = select.args.get("from_")
            table = from_.this if from_ is not None else None
            joins = table.args.get("joins") if isinstance(table, _exp.Table) else None
            if joins:
                table.set("joins", None)
                select.set("joins", [*joins, *(select.args.get("joins") or [])])
                select.meta[FROM_FIRST_JOINS_KEY] = True
    return trees


def _wrap_nested_joins(trees: list[Expression]) -> list[Expression]:
    """Parenthesize a nested join written without parentheses.

    In ``t JOIN u JOIN v ON v.id = u.id ON u.id = t.id`` sqlglot puts
    ``JOIN v`` in the ``joins`` arg of the joined table ``u``, which the
    generator doesn't render, so the join was dropped. The parenthesized form,
    ``t JOIN (u JOIN v ON v.id = u.id) ON u.id = t.id``, means the same and
    parses to the same table wrapped in a subquery node, so it's rewritten to
    that.
    """
    for tree in trees:
        if tree is None:
            continue
        nested = [
            join
            for join in tree.find_all(_exp.Join)
            if isinstance(join.this, _exp.Table) and join.this.args.get("joins")
        ]
        for join in nested:
            join.set("this", _exp.Subquery(this=join.this))
    return trees


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
    return _wrap_nested_joins(_hoist_from_table_joins(trees)), errors
