"""Custom DuckDB SQL generator with full control over formatting style.

Subclasses sqlglot's DuckDBGenerator to enforce jarify's opinionated rules:
- Configurable indentation width
- Leading-comma style: ,col aligned with content at pad+1
- Bare JOIN → INNER JOIN normalization
- LEFT/RIGHT OUTER JOIN → LEFT/RIGHT JOIN (or the reverse with explicit_outer_join)
- AND/OR conditions always on separate lines in pretty mode
- WHERE/HAVING/ON: first condition inline with keyword, AND/OR right-justified
  so all condition content aligns at the same column; = operators in WHERE
  top-level AND conditions are column-aligned (padded to max LHS width + 1)
- CTE: opening paren on its own line, comma-prefix separator
- Consistent keyword casing; DuckDB functions in lowercase
- IS NOT NULL preserved (not rewritten to NOT x IS NULL)
- NOT IN / NOT BETWEEN / NOT SIMILAR TO / NOT GLOB keep NOT after the operand
- NULLS LAST/FIRST suppressed when it matches DuckDB's default
- SELECT * FROM t → FROM t (DuckDB FROM-first syntax)
- JSON extraction casts keep grouping: (json_expr->'path')::type
- Dynamic JSON extraction paths stay as function calls; only static paths use -> / ->>
- Struct tuple casts (val, ...)::type use leading-comma style when multi-line
- DISTINCT inside aggregates appears on its own line when the call wraps
- An aggregate's ORDER BY goes on its own line, below its arguments, when the call wraps
- CREATE TABLE: opening paren on its own line, column name/type alignment,
  blank line before table-level constraints
- Aggregate and window functions (COUNT, SUM, ROW_NUMBER, RANK, …) are uppercase;
  all other DuckDB built-in functions remain lowercase, unless a name is listed in
  the uppercase_functions / lowercase_functions config
- FROM/JOIN block: AS omitted from table aliases; ON/USING inline; aliases
  column-aligned when the block contains only simple (single-line) table refs
- A -- comment never swallows SQL: commented windows, calls and IN lists take
  their multi-line form; any other comment followed by SQL becomes /* */
- A CASE is always multi-line, laid out relative to the column its CASE
  keyword starts in, wherever it appears
"""

from __future__ import annotations

import contextlib
import functools
import re
import typing as t
from typing import TYPE_CHECKING, ClassVar

import sqlglot.expressions as exp
from sqlglot.dialects.dialect import groupconcat_sql as _groupconcat_sql
from sqlglot.dialects.duckdb import DuckDB
from sqlglot.helper import name_sequence

from jarify.parser import (
    _IFNULL_SENTINEL,
    CTE_COMMENTS_AFTER_AS,
    FROM_FIRST_JOINS_KEY,
    all_keyword_comments,
    keyword_comments,
)

if TYPE_CHECKING:
    from jarify.config import JarifyConfig

# Lines inside a multi-line block comment start with a mark while the tree is
# generated.  Enclosing blocks indent every line of their body, comment lines
# included, which shifted those lines further right on every pass;
# restore_comment_lines() drops the added indentation along with the marks.
# On a line that starts with a space the mark replaces that space, so the
# widths the layout measures stay the same.
_COMMENT_SPACE_MARK = "\x00"
_COMMENT_LINE_MARK = "\x01"
_MARKED_COMMENT_LINE_RE = re.compile(f"\n[ \t]*([{_COMMENT_SPACE_MARK}{_COMMENT_LINE_MARK}])")


def _mark_comment_lines(comment: str) -> str:
    return re.sub(r"\n( ?)", lambda m: "\n" + (_COMMENT_SPACE_MARK if m.group(1) else _COMMENT_LINE_MARK), comment)


def restore_comment_lines(sql: str) -> str:
    """Put the lines of multi-line block comments back exactly as written."""
    return _MARKED_COMMENT_LINE_RE.sub(lambda m: "\n " if m.group(1) == _COMMENT_SPACE_MARK else "\n", sql)


# A CASE is laid out relative to the column its CASE keyword starts in, as in
# a SELECT list: a searched CASE's WHEN / THEN / ELSE two columns past the C
# and END under it; a simple CASE's WHEN / ELSE one column past the C and END
# one column before it, under the leading comma (with trailing commas, a
# simple CASE's END goes under the C too). case_sql() can't know that column,
# since whatever encloses the CASE may put text before it on its line
# (`WHERE `, `THEN `, `a || `). So it lays the CASE out for the column a
# SELECT list gives it and marks the C of CASE and the E of END. Once the
# statement is rendered, _anchor_cases() moves each CASE's lines by the
# difference between the column its CASE landed in and the one they were laid
# out for. Each mark replaces its letter, so widths stay the same.
_CASE_MARK = "\U00100000"  # the C of a CASE whose END goes under it
_SIMPLE_CASE_MARK = "\U00100001"  # the C of a CASE whose END goes one column before it
_END_MARK = "\U00100002"  # the E of a CASE's END
_CASE_MARK_RE = re.compile(f"[{_CASE_MARK}{_SIMPLE_CASE_MARK}{_END_MARK}]")
_CASE_UNMARK = str.maketrans({_CASE_MARK: "C", _SIMPLE_CASE_MARK: "C", _END_MARK: "E"})


def _case_line_shifts(lines: list[str], start_col: int) -> list[int]:
    """Return how many columns anchoring moves each line right (left when negative).

    *start_col* is the column the first line starts in; the other lines'
    columns are their own. A CASE's lines run from the line after its CASE to
    its END. An enclosing CASE is anchored before the CASEs inside it, so they
    are measured where it moved them.
    """
    shifts = [0] * len(lines)
    pairs: list[tuple[int, int, int, int, bool]] = []
    opened: list[tuple[int, int, bool]] = []
    for row, line in enumerate(lines):
        for mark in _CASE_MARK_RE.finditer(line):
            if mark.group() != _END_MARK:
                opened.append((row, mark.start(), mark.group() == _SIMPLE_CASE_MARK))
            elif opened:
                case_row, case_index, simple = opened.pop()
                pairs.append((case_row, case_index, row, mark.start(), simple))
    for case_row, case_index, end_row, end_index, simple in sorted(pairs):
        case_col = case_index + shifts[case_row] + (start_col if case_row == 0 else 0)
        end_col = end_index + shifts[end_row]
        # The lines expect the CASE where END is, or one column right of it.
        delta = case_col - (end_col + simple)
        for row in range(case_row + 1, end_row + 1):
            shifts[row] += delta
    return shifts


def _anchor_cases(sql: str, start_col: int = 0) -> str:
    """Lay every marked CASE in *sql* out relative to the column its CASE keyword is in.

    *start_col* is the column *sql*'s first line starts in.
    """
    if _END_MARK not in sql:
        return sql
    lines = sql.split("\n")
    anchored = []
    for line, shift in zip(lines, _case_line_shifts(lines, start_col), strict=True):
        if shift > 0 and line:
            line = " " * shift + line
        elif shift < 0:
            line = line[min(-shift, len(line) - len(line.lstrip(" "))) :]
        anchored.append(line)
    return "\n".join(anchored).translate(_CASE_UNMARK)


def _last_line_case_shift(sql: str, start_col: int) -> int:
    """Return how many columns _anchor_cases() will move the last line of *sql* right."""
    if _END_MARK not in sql:
        return 0
    return _case_line_shifts(sql.split("\n"), start_col)[-1]


# Column-alias alignment measures where each SELECT list and star REPLACE /
# RENAME list starts once the statement is rendered (see
# JarifyGenerator._measure_alias_prefixes). Each such list is numbered in its
# node's meta, and while measuring, the leader character that starts the
# list's first line is swapped for a mark: one character from Unicode's
# supplementary private use area, offset by the list's number, so widths
# stay the same.
_ALIAS_LIST_KEY = "jarify_alias_list"
_ALIAS_LIST_MARK_BASE = 0xF0000
_ALIAS_LIST_MARK_LAST = 0xFFFFD
_ALIAS_LIST_MARK_RE = re.compile(f"[{chr(_ALIAS_LIST_MARK_BASE)}-{chr(_ALIAS_LIST_MARK_LAST)}]")
# Measuring passes before jarify settles for the last prefixes measured. A
# second pass is needed only when the first pass's estimate was wrong.
_ALIAS_PREFIX_PASSES = 3


def _jarify_struct_sql(self: JarifyGenerator, expression: exp.Struct) -> str:
    """Render struct literals as {key: val, ...}, wrapping to multiple lines when too wide.

    Replaces DuckDB's ``_struct_sql`` which always emits an inline string.  When
    the flat representation exceeds ``max_text_width`` jarify produces a
    leading-comma multi-line form instead, e.g.::

        {
           'key':   x.key
          ,'other': x.other
        }
    """
    ancestor_cast = expression.find_ancestor(exp.Cast, exp.Select)
    ancestor_cast = None if isinstance(ancestor_cast, exp.Select) else ancestor_cast

    if not expression.expressions and isinstance(ancestor_cast, exp.Cast) and ancestor_cast.to.is_type(exp.DType.MAP):
        return "MAP()"

    is_bq_inline_struct = (
        expression.find(exp.PropertyEQ) is None
        and ancestor_cast
        and any(casted_type.is_type(exp.DType.STRUCT) for casted_type in ancestor_cast.find_all(exp.DataType))
    )

    args: list[str] = []
    for i, expr in enumerate(expression.expressions):
        is_property_eq = isinstance(expr, exp.PropertyEQ)
        this = expr.this
        value = expr.expression if is_property_eq else expr

        if is_bq_inline_struct:
            args.append(self.sql(value))
        else:
            if isinstance(this, exp.Identifier):
                key = self.sql(exp.Literal.string(expr.name))
            elif is_property_eq:
                key = self.sql(this)
            else:
                key = self.sql(exp.Literal.string(f"_{i}"))
            args.append(f"{key}: {self.sql(value)}")

    if is_bq_inline_struct:
        return f"ROW({', '.join(args)})"

    if not self.pretty or not self.too_wide(args):
        return f"{{{', '.join(args)}}}"

    # Multi-line leading-comma form
    parts = [f" {args[0]}"]
    parts.extend(f",{a}" for a in args[1:])
    inner = self.indent("\n" + "\n".join(parts) + "\n", skip_first=True, skip_last=True)
    return f"{{{inner}}}"


class JarifyGenerator(DuckDB.Generator):
    """Opinionated DuckDB SQL generator for jarify."""

    # DuckDB's TRANSFORMS maps exp.Pivot to a preprocess([unqualify_columns]) transform,
    # which strips all table qualifiers from columns inside PIVOT subqueries.
    # We remove it so the dispatch falls through to pivot_sql directly, preserving qualifiers.
    #
    # We also remove exp.ArrayContains so dispatch falls through to arraycontains_sql,
    # which emits `list_contains` (DuckDB's canonical name) instead of `array_contains`.
    #
    # We also remove exp.JSONExtract so dispatch falls through to jsonextract_sql, which
    # renders -> and ->> without surrounding spaces (DuckDB style: value->>'key').
    #
    # We also remove exp.GroupConcat so dispatch falls through to groupconcat_sql, which
    # emits `string_agg` (PostgreSQL-compatible) instead of the Oracle-style `listagg` alias.
    TRANSFORMS: ClassVar[dict] = {
        **{
            k: v
            for k, v in DuckDB.Generator.TRANSFORMS.items()
            if k not in (exp.Pivot, exp.ArrayContains, exp.JSONExtract, exp.GroupConcat)
        },
        # Override DuckDB's _struct_sql so struct literals wrap when they exceed
        # max_line_length.  DuckDB's built-in version always emits a flat string.
        exp.Struct: _jarify_struct_sql,
    }

    # Comments on QUALIFY go above it, as they do above WHERE and HAVING.
    WITH_SEPARATED_COMMENTS: ClassVar[tuple[type[exp.Expr], ...]] = (
        *DuckDB.Generator.WITH_SEPARATED_COMMENTS,
        exp.Qualify,
    )
    # _cte_sql_parts writes a CTE's comments itself.
    EXCLUDE_COMMENTS: ClassVar[tuple[type[exp.Expr], ...]] = (*DuckDB.Generator.EXCLUDE_COMMENTS, exp.CTE)

    # Aggregate and window function names that should be uppercased in output.
    # Derived from sqlglot's AggFunc hierarchy + RowNumber (window-only) + the
    # DuckDB-dialect names for functions that get renamed by the dialect layer
    # (e.g. VariancePop → "var_pop", PercentileCont → "quantile_cont").
    _UPPERCASE_FUNCS: ClassVar[frozenset[str]] = (
        frozenset(
            cls.sql_name().lower()
            for _, cls in vars(exp).items()
            if isinstance(cls, type) and issubclass(cls, exp.AggFunc) and cls is not exp.AggFunc
        )
        | frozenset(["row_number"])
        | frozenset(
            [
                # DuckDB renames these aggregate expressions; add the dialect output
                # names so normalize_func can uppercase them too.
                "approx_count_distinct",  # ApproxDistinct
                "bool_and",  # LogicalAnd
                "bool_or",  # LogicalOr
                "boolxor",  # BoolxorAgg
                "json_arrayagg",  # JSONArrayAgg
                "json_group_object",  # JSONObjectAgg / JSONBObjectAgg
                "string_agg",  # GroupConcat (prefer string_agg over listagg alias)
                "quantile_cont",  # PercentileCont
                "quantile_disc",  # PercentileDisc
                "var_pop",  # VariancePop
            ]
        )
    )

    def __init__(self, config: JarifyConfig) -> None:
        super().__init__(
            pretty=True,
            indent=config.indent,
            leading_comma=config.leading_commas,
            normalize=False,  # we manage casing ourselves
            normalize_functions="lower",  # DuckDB functions stay lowercase
            max_text_width=config.max_line_length,
            comments=True,
            dialect="duckdb",  # tells generator to skip default NULLS ordering
        )
        self._config = config
        self._uppercase_func_overrides = frozenset(name.lower() for name in config.uppercase_functions)
        self._lowercase_func_overrides = frozenset(name.lower() for name in config.lowercase_functions)
        self._as_align_width: int | None = None  # set during SELECT expression rendering
        self._tree_as_align_column: int | None = None  # visible AS column target per statement tree during generate()
        self._alias_prefixes: dict[int, int] = {}  # measured text column of each aligned list, by list number
        self._alias_probe: dict[int, set[int]] | None = None  # while measuring: prefixes each list was given
        self._col_name_align: int | None = None  # set during CREATE TABLE column rendering
        self._col_type_align: int | None = None  # set during CREATE TABLE column rendering
        self._join_alias_col: int | None = None  # set during FROM/JOIN block rendering
        self._leading_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._trailing_sep_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._closing_paren_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._connector_force_expand: bool = False  # set True inside WHERE/HAVING to always break AND/OR
        self._block_comment_texts: frozenset[str] = frozenset()  # comments generate() renders as /* */
        self._statement: exp.Expr | None = None  # the tree super().generate() is rendering
        self._pretty_statement: bool = False  # True while a pretty statement renders, even where pretty is off

    def preprocess(self, expression: exp.Expr) -> exp.Expr:
        expression = super().preprocess(expression)
        self._statement = expression
        return expression

    def sql(self, expression: str | exp.Expr | None, key: str | None = None, comment: bool = True) -> str:
        sql = super().sql(expression, key, comment)
        if key is None and expression is not None and expression is self._statement:
            # The whole statement is rendered, so every CASE's column is known.
            # Anchor them before generate() puts back the line breaks inside
            # string literals, which aren't lines of the layout.
            sql = _anchor_cases(sql)
        return sql

    def _replace_line_breaks(self, string: str) -> str:
        # generate() turns a pretty statement's sentinels back into line
        # breaks once the layout is done, so indenting can't change a string
        # literal.  Parts rendered compactly switch pretty off, which would
        # leave their literals' line breaks to be indented, so protect them
        # too.
        if self._pretty_statement:
            return string.replace("\n", self.SENTINEL_LINE_BREAK)
        return super()._replace_line_breaks(string)

    def generate(self, expression: exp.Expr, copy: bool = True) -> str:
        """Generate SQL, never letting a -- comment swallow SQL after it.

        Commented constructs that fit on one line get a multi-line layout where
        jarify has one. A comment still followed by SQL on its line (e.g. inside
        a binary expression: ``a /* note */ + 1``) is rendered as a block
        comment instead, and the statement is generated again so alignment
        accounts for the block comment's width.
        """
        # Comments that already contain /* or */ can't become block comments.
        texts = {
            c.strip()
            for node in expression.walk()
            for c in [*(node.comments or []), *all_keyword_comments(node)]
            if c.strip() and "\n" not in c and "/*" not in c and "*/" not in c
        }
        pristine = expression.copy() if texts else expression
        sql = self._generate_once(expression, copy=copy)
        blocked: set[str] = set()
        for _ in range(3):
            swallowing = self._swallowing_comment_texts(sql, texts - blocked)
            if not swallowing:
                break
            blocked |= swallowing
            saved = self._block_comment_texts
            self._block_comment_texts = frozenset(blocked)
            try:
                sql = self._generate_once(pristine.copy(), copy=False)
            finally:
                self._block_comment_texts = saved
        return sql

    def _generate_once(self, expression: exp.Expr, copy: bool) -> str:
        if not self.pretty:
            return restore_comment_lines(super().generate(expression, copy=copy))
        saved_align, saved_prefixes = self._tree_as_align_column, self._alias_prefixes
        saved_pretty_statement = self._pretty_statement
        if copy:
            expression = expression.copy()
        try:
            self._pretty_statement = True
            self._alias_prefixes = self._measure_alias_prefixes(expression)
            self._tree_as_align_column = self._compute_tree_as_align_column(expression)
            return restore_comment_lines(super().generate(expression, copy=False))
        finally:
            self._tree_as_align_column, self._alias_prefixes = saved_align, saved_prefixes
            self._pretty_statement = saved_pretty_statement

    def _measure_alias_prefixes(self, expression: exp.Expr) -> dict[int, int]:
        """Return the column each aligned list's text starts in, by list number.

        Aligning ``AS`` to a visible column needs the width of everything
        before a list's text on its lines. That indentation comes from
        whatever encloses the list (CTE and subquery parentheses, a macro
        body, a star's REPLACE block) and is known only once the statement
        is rendered. So the statement is rendered with each list's first
        line marked (see ``_mark_alias_list``), and the columns the marks
        land in are read back. When those differ from the prefixes the
        rendering used, it is rendered again with the measured ones. The
        marked output is thrown away; the caller renders the statement again
        with the prefixes returned here.

        Lists are numbered in node meta, which copies keep, so a list still
        matches its measurement when rendering goes through a copy (a bare
        JOIN's INNER JOIN copy, the FROM-first copy of a SELECT). A
        statement with fewer than two column aliases aligns nothing, so it
        isn't measured. Each measuring pass names unnamed table aliases
        (``_t0``, ``_t1``, …) from its own sequence, so the caller's
        rendering gets the names it would get without measuring.
        """
        aliases = sum(isinstance(alias.parent, (exp.Select, exp.Star)) for alias in expression.find_all(exp.Alias))
        if aliases < 2:
            return {}
        for number, node in enumerate(expression.find_all(exp.Select, exp.Star)):
            node.meta[_ALIAS_LIST_KEY] = number

        outer_align, next_name = self._tree_as_align_column, self._next_name
        prefixes: dict[int, int] = {}
        for _ in range(_ALIAS_PREFIX_PASSES):
            self._alias_prefixes = prefixes
            self._alias_probe = {}
            self._next_name = name_sequence("_t")
            try:
                tree = expression.copy()
                self._tree_as_align_column = self._compute_tree_as_align_column(tree)
                sql = super().generate(tree, copy=False)
                used = self._alias_probe
            finally:
                self._alias_probe = None
                self._tree_as_align_column, self._next_name = outer_align, next_name

            measured: dict[int, int] = {}
            for line in sql.split("\n"):
                for mark in _ALIAS_LIST_MARK_RE.finditer(line):
                    number = ord(mark.group()) - _ALIAS_LIST_MARK_BASE
                    if number in used:
                        measured.setdefault(number, mark.start() + 1)
            if all(used[number] == {prefix} for number, prefix in measured.items()):
                break
            prefixes = {**prefixes, **measured}
        return prefixes

    def _alias_list_prefix(self, node: exp.Expr, estimate: int) -> int:
        """Return the measured text column of the list ``node`` heads, else ``estimate``."""
        number = node.meta_get(_ALIAS_LIST_KEY)
        if number is None:
            return estimate
        prefix = self._alias_prefixes.get(number, estimate)
        if self._alias_probe is not None:
            self._alias_probe.setdefault(number, set()).add(prefix)
        return prefix

    def _mark_alias_list(self, node: exp.Expr, sql: str) -> str:
        """While measuring, swap the leader that starts a list's first line for the list's mark."""
        number = node.meta_get(_ALIAS_LIST_KEY)
        if self._alias_probe is None or number is None or not sql:
            return sql
        if _ALIAS_LIST_MARK_BASE + number > _ALIAS_LIST_MARK_LAST:
            return sql
        return chr(_ALIAS_LIST_MARK_BASE + number) + sql[1:]

    @staticmethod
    def _swallowing_comment_texts(sql: str, texts: set[str]) -> set[str]:
        """Return the comment texts rendered as ``-- text`` with SQL after them on the same line.

        Other comments after it don't count: only SQL that the comment would
        swallow does.
        """

        def candidates(rest: str) -> list[str]:
            """Known comment texts that the text after a ``--`` could be."""
            rest = rest.removeprefix(" ")
            return [x for x in texts if rest.startswith(x)]

        @functools.cache
        def only_comments(tail: str) -> bool:
            """True when tail holds nothing but comments (or nothing at all)."""
            tail = tail.lstrip()
            if not tail:
                return True
            if tail.startswith("/*"):
                end = tail.find("*/")
                return end == -1 or only_comments(tail[end + 2 :])
            if tail.startswith("--"):
                rest = tail[2:].removeprefix(" ")
                return any(only_comments(rest[len(x) :]) for x in candidates(rest)) or not candidates(rest)
            return False

        found: set[str] = set()
        if not texts:
            return found
        for line in sql.split("\n"):
            start = line.find("--")
            while start != -1:
                rest = line[start + 2 :].removeprefix(" ")
                matches = candidates(rest)
                if matches and not any(only_comments(rest[len(x) :]) for x in matches):
                    found.update(matches)
                start = line.find("--", start + 2)
        return found

    # ------------------------------------------------------------------
    # Function name casing: aggregates/window functions → UPPER, rest → lower.
    # The uppercase_functions / lowercase_functions config lists override the
    # built-in classification for the name as finally written (after
    # canonical renames such as array_agg → list).
    # ------------------------------------------------------------------

    def normalize_func(self, name: str) -> str:
        if name.lower() == _IFNULL_SENTINEL:
            # The formatter masks ifnull as a same-length sentinel before parsing;
            # emit the real name so its configured case applies.
            name = "ifnull"
        key = name.lower()
        if key in self._uppercase_func_overrides:
            return name.upper()
        if key in self._lowercase_func_overrides:
            return key
        return name.upper() if key in self._UPPERCASE_FUNCS else key

    # ------------------------------------------------------------------
    # Comment rendering: use -- for single-line, /* */ for multi-line
    # ------------------------------------------------------------------

    def maybe_comment(
        self,
        sql: str,
        expression: exp.Expr | None = None,
        comments: list[str] | None = None,
        separated: bool = False,
    ) -> str:
        if comments is None:
            comments = expression.comments if expression else None
        effective = comments if self.comments else None
        if not effective or (expression is not None and isinstance(expression, self.EXCLUDE_COMMENTS)):
            return sql
        is_separated = separated or isinstance(expression, self.WITH_SEPARATED_COMMENTS)
        rendered = self._render_comments(effective, leading=is_separated)
        if not rendered:
            return sql
        if is_separated:
            sep = self.sep()
            return f"{sep}{rendered}{sql}" if not sql or sql[0].isspace() else f"{rendered}{sep}{sql}"
        return f"{sql}{rendered}"

    # ------------------------------------------------------------------
    # Leading-comma style: ,col  (comma at pad, content at pad+1)
    # ------------------------------------------------------------------

    def expressions(
        self,
        expression: exp.Expr | None = None,
        key: str | None = None,
        sqls: t.Collection[str | exp.Expr] | None = None,
        flat: bool = False,
        indent: bool = True,
        skip_first: bool = False,
        skip_last: bool = False,
        sep: str = ", ",
        prefix: str = "",
        dynamic: bool = False,
        new_line: bool = False,
    ) -> str:
        if not (self.pretty and self.leading_comma) or isinstance(expression, (exp.Properties, exp.DataType)):
            return super().expressions(
                expression=expression,
                key=key,
                sqls=sqls,
                flat=flat,
                indent=indent,
                skip_first=skip_first,
                skip_last=skip_last,
                sep=sep,
                prefix=prefix,
                dynamic=dynamic,
                new_line=new_line,
            )

        expressions_list = expression.args.get(key or "expressions") if expression else sqls

        if not expressions_list:
            return ""

        if flat:
            return sep.join(sql for sql in (self.sql(e) for e in expressions_list) if sql)

        # Compute AS alignment for direct SELECT expression lists
        is_select = isinstance(expression, exp.Select) and key is None
        saved_align = self._as_align_width
        if is_select:
            select_expression = t.cast(exp.Select, expression)
            prefix_width = self._select_expression_prefix_width(select_expression)
            self._as_align_width = (
                self._tree_as_align_column - prefix_width
                if self._tree_as_align_column is not None
                else self._snap_to_alias_guide(
                    self._compute_as_align_width(list(expressions_list), prefix_width=prefix_width),
                    prefix_width=prefix_width,
                )
            )

        try:
            result_sqls = []
            for i, e in enumerate(expressions_list):
                sql = self.sql(e, comment=False)
                if not sql:
                    continue
                leader = " " if i == 0 else ","
                if (
                    isinstance(e, exp.Expr)
                    and e.comments
                    and (self._leading_comment_texts or self._trailing_sep_comment_texts)
                ):
                    trail_sep = [c for c in e.comments if c.strip() in self._trailing_sep_comment_texts]
                    # Both sets match comments by text, so a comment written in
                    # two places can be in both; write it once, after the column.
                    lead = [
                        c
                        for c in e.comments
                        if c.strip() in self._leading_comment_texts
                        and c.strip() not in self._trailing_sep_comment_texts
                    ]
                    trail = [
                        c
                        for c in e.comments
                        if c.strip() not in self._leading_comment_texts
                        and c.strip() not in self._trailing_sep_comment_texts
                    ]
                    # Own-line comments keep a line of their own; a multi-line
                    # block comment keeps its lines as written.
                    for c in lead:
                        result_sqls.append(f" {prefix}{self._render_comments([c], leading=True)}")
                    inline = self._render_comments(trail)
                    result_sqls.append(f"{leader}{prefix}{sql}{inline}")
                    for c in trail_sep:
                        result_sqls.append(f"{prefix}{self._render_comments([c], leading=True)}")
                else:
                    inline = self._inline_comments(e) if isinstance(e, exp.Expr) else ""
                    result_sqls.append(f"{leader}{prefix}{sql}{inline}")
        finally:
            self._as_align_width = saved_align

        if is_select and result_sqls:
            result_sqls[0] = self._mark_alias_list(t.cast(exp.Select, expression), result_sqls[0])
        result_sql = "\n".join(s.rstrip() for s in result_sqls)
        # dynamic=True means "wrap only if necessary" — stay inline when content fits.
        # Commented items never go inline: a -- comment would swallow the rest of the line.
        # Nor does an item holding a CASE, which is always multi-line: like a
        # call's argument, it goes on a line of its own.
        commented = dynamic and any(
            isinstance(e, exp.Expr) and (self._has_comments(e) or self._holds_case(e)) for e in expressions_list
        )
        if dynamic and not commented and not self.too_wide(result_sqls):
            return sep.join(s.lstrip(",").lstrip() for s in result_sqls)
        if dynamic and new_line:
            if not commented and sep.strip() != ",":
                # Space-separated clauses, such as a PIVOT's `FOR col IN (…)`
                # fields, stay on their line; each one wraps on its own.
                return sep.join(s.lstrip(",").lstrip() for s in result_sqls)
            # A bracketed list that doesn't fit, such as an IN list or a list
            # literal, puts its items between their own ( and ) lines, like
            # wrapped call arguments. That also keeps the last item's comment
            # from swallowing the ")".
            return self.indent("\n" + result_sql + "\n", skip_first=True, skip_last=True)
        return self.indent(result_sql, skip_first=skip_first, skip_last=skip_last) if indent else result_sql

    def _inline_comments(self, expression: exp.Expr) -> str:
        """Render inline comments using -- for single-line, /* */ for multi-line."""
        if not self.comments or not expression.comments:
            return ""
        return self._render_comments(expression.comments)

    def _render_comments(self, comments: list[str], *, leading: bool = False) -> str:
        if not self.comments or not comments:
            return ""
        parts = []
        for c in comments:
            if not c or not c.strip():
                continue
            if "\n" in c:
                parts.append(f"/*{_mark_comment_lines(c)}*/")
            elif c.strip() in self._block_comment_texts:
                parts.append(f"/* {c.strip()} */")
            else:
                parts.append(f"-- {c.strip()}")
        if not parts:
            return ""
        # A `--` comment runs to the end of its line, so each comment gets its
        # own line: joining them with spaces would comment out the ones after.
        if leading:
            return "\n".join(parts)
        return " " + "\n".join(parts)

    def _compute_as_align_width(self, expressions_list: list, *, prefix_width: int = 0) -> int | None:
        """Compute the column width for AS alignment in a SELECT expression list.

        Returns None if alignment should not be applied (< 2 aliases total).

        Multi-line aliased expressions (e.g. CASE … END AS foo) participate in
        alignment using the width of their closing line (typically ``END``), so
        the trailing ``AS`` can align with single-line aliases in the same
        SELECT list.
        """
        col_widths, alias_count = self._collect_as_alignment_metrics(expressions_list)
        if alias_count < 2:
            return None
        align_width = max(col_widths)
        min_column_alias = self._config.min_column_alias
        if min_column_alias is None:
            return align_width
        return max(align_width, max(0, min_column_alias - prefix_width))

    def _compute_tree_as_align_column(self, expression: exp.Expr) -> int | None:
        """Compute one visible AS column across the query-wide CTE/select tree."""
        as_columns: list[int] = []
        alias_count = 0
        for select in self._iter_query_aligned_selects(expression):
            widths, aliases = self._collect_as_alignment_metrics(list(select.expressions))
            prefix_width = self._select_expression_prefix_width(select)
            as_columns.extend(prefix_width + width for width in widths)
            alias_count += aliases

        if alias_count < 2 or not as_columns:
            return None

        align_column = max(as_columns)
        min_column_alias = self._config.min_column_alias
        if min_column_alias is not None:
            align_column = max(align_column, min_column_alias)
        return self._snap_to_alias_guide(align_column)

    def _snap_to_alias_guide(self, align_width: int | None, *, prefix_width: int = 0) -> int | None:
        """Push an AS alignment target right so ``AS`` starts on a visual guide.

        ``prefix_width + align_width`` is the 0-based index of the space before
        ``AS``, so ``AS`` itself starts in 1-based editor column
        ``prefix_width + align_width + 2``. With ``alias_visual_guide_interval``
        set to ``n``, that column is rounded up to the next multiple of ``n``;
        a column already on a guide stays put. Returns ``align_width``
        unchanged when no interval is configured.
        """
        interval = self._config.alias_visual_guide_interval
        if align_width is None or interval is None:
            return align_width
        as_column = prefix_width + align_width + 2
        guide_column = -(-as_column // interval) * interval
        return guide_column - 2 - prefix_width

    def _iter_query_aligned_selects(self, expression: exp.Expr) -> t.Iterator[exp.Select]:
        """Yield SELECTs that share query-wide alias alignment.

        Query-wide alignment spans the main SELECT plus any CTE-body SELECTs,
        including nested CTEs. It intentionally excludes unrelated subqueries in
        expressions or JOINs, which keep their local alignment behavior.

        When ``expression`` is not itself a SELECT (e.g. a CREATE MACRO wrapping
        a ``WITH … SELECT`` body) we walk into the statement to find the inner
        SELECT that owns the top-level WITH clause, then recurse from there so
        that all CTEs inside the statement share a single alignment column.
        """
        if isinstance(expression, exp.Select):
            yield expression
            with_ = expression.args.get("with_")
            if isinstance(with_, exp.With):
                for cte in with_.expressions:
                    if isinstance(cte, exp.CTE) and isinstance(cte.this, exp.Select):
                        yield from self._iter_query_aligned_selects(cte.this)
        else:
            # Non-Select wrapper (e.g. CREATE OR REPLACE MACRO … AS TABLE (…)):
            # find the inner SELECT that owns the WITH clause and treat it as
            # the root of the query-aligned tree.
            for node in expression.walk():
                if isinstance(node, exp.Select) and node.args.get("with_"):
                    yield from self._iter_query_aligned_selects(node)
                    return

    def _select_expression_prefix_width(self, select: exp.Select) -> int:
        """Return visible prefix width before a SELECT-list expression.

        That's the 0-based column the expressions' text starts in, as
        ``_measure_alias_prefixes`` measured it in the rendered statement.
        Before it's measured, it's estimated: each expression line gets the
        generator pad plus the leading-comma marker (` ` for the first row,
        `,` for subsequent rows), and every ancestor SELECT adds one indent
        level. That's right for a top-level query and its CTEs, not for every
        context (a macro body, a CTE of a UNION), which the measurement
        corrects.
        """
        ancestor_selects = 0
        parent = select.parent
        while parent is not None:
            if isinstance(parent, exp.Select):
                ancestor_selects += 1
            parent = parent.parent
        return self._alias_list_prefix(select, self.pad + 1 + (ancestor_selects * self._indent))

    @property
    def _list_item_column(self) -> int:
        """The column a list item's text starts in, relative to its lines: after the leader with leading commas."""
        return 1 if self.leading_comma else 0

    def _star_list_prefix_width(self, star: exp.Star) -> int:
        """Return the visible prefix width before a star's REPLACE or RENAME expressions.

        Measured like a SELECT list's. The estimate: ``star_sql`` puts the
        lists three columns right of the star, which starts where the
        enclosing SELECT list's text does.
        """
        parent = star.parent
        select_prefix = self._select_expression_prefix_width(parent) if isinstance(parent, exp.Select) else self.pad + 1
        return self._alias_list_prefix(star, select_prefix + 3)

    def _collect_as_alignment_metrics(self, expressions_list: list) -> tuple[list[int], int]:
        """Return ``(column_widths, alias_count)`` for a SELECT expression list.

        For single-line aliased expressions the width is simply ``len(col_sql)``.
        For multi-line aliased expressions (e.g. scalar subqueries, CASE blocks)
        the effective width is ``max(0, len(last_line) - 1)``, measuring the
        last line with its indentation (a CASE's ``END`` is indented, and
        further when the CASE starts partway along its first line), as
        ``alias_sql`` does.

        The ``-1`` adjustment exists because ``alias_sql`` adds ``+1`` to the
        padding for multi-line expressions in order to compensate for the
        missing leader character on continuation lines (the `` ``/``,`` leader
        is only prepended to the *first* line of an expression by the
        ``expressions()`` loop, not subsequent lines including the last).  When
        a SELECT list contains *only* multi-line expressions there is no
        single-line expression to drive ``align_width`` higher, so without the
        ``-1`` correction the ``+1`` in ``alias_sql`` causes a spurious extra
        space before ``AS`` (yielding ``), 1)  AS alias`` instead of the
        expected ``), 1) AS alias``).
        """
        col_widths: list[int] = []
        alias_count = 0
        for e in expressions_list:
            if isinstance(e, exp.Alias):
                alias_count += 1
                col_sql = self.sql(e.this)
                if self._ends_in_literal_lines(col_sql):
                    continue  # aligns on its own, see alias_sql
                if "\n" in col_sql:
                    last_line = col_sql.splitlines()[-1]
                    # Subtract 1: cancels the +1 compensation in alias_sql so that
                    # SELECT lists with only multi-line expressions don't produce a
                    # spurious extra space before AS. Measure the last line where
                    # anchoring a CASE will put it (`a || CASE … END` moves it right).
                    shift = _last_line_case_shift(col_sql, self._list_item_column)
                    col_widths.append(max(0, len(last_line) - 1 + shift))
                else:
                    col_widths.append(len(col_sql))
            else:
                # Non-aliased single-line columns count toward the alignment
                # width so AS keywords clear the longest expression in the list.
                # Measure without comments, as expressions() renders the column:
                # a comment after it or on its own line shouldn't move the AS.
                col_sql = self.sql(e, comment=False)
                if "\n" not in col_sql and not self._ends_in_literal_lines(col_sql):
                    col_widths.append(len(col_sql))

        return col_widths, alias_count

    # ------------------------------------------------------------------
    # Alias: align AS keyword when _as_align_width is set
    # ------------------------------------------------------------------

    def alias_sql(self, expression: exp.Alias) -> str:
        this_sql = self.sql(expression, "this")
        alias_name = self.sql(expression, "alias")
        if not alias_name:
            return this_sql
        align_width = self._as_align_width
        # A SELECT rendered compactly, such as a short scalar subquery, aligns
        # nothing; the width set for an enclosing list doesn't apply to it.
        aligned = self.pretty and not self._ends_in_literal_lines(this_sql)
        if align_width is not None and aligned and isinstance(expression.parent, (exp.Select, exp.Star)):
            if "\n" in this_sql:
                lines = this_sql.splitlines()
                # For multi-line expressions the last line (e.g. ``)``, ``END``)
                # has no leader character prepended in the expressions loop
                # (the `` ``/``,`` leader only goes on the first line).  To land
                # ``AS`` at the same visual column as single-line aliases — which
                # DO carry a 1-char leader — we add an extra +1 to the padding.
                # Measure the last line where anchoring a CASE will put it.
                width = len(lines[-1]) + _last_line_case_shift(this_sql, self._list_item_column)
                padding = " " * max(0, align_width - width + 1)
                lines[-1] = f"{lines[-1]}{padding} AS {alias_name}"
                return "\n".join(lines)
            padding = " " * max(0, align_width - len(this_sql))
            return f"{this_sql}{padding} AS {alias_name}"
        return f"{this_sql} AS {alias_name}"

    def _ends_in_literal_lines(self, sql: str) -> bool:
        """Whether the last line of *sql* ends inside a string literal's lines.

        A literal's lines after its first are written as they are, starting at
        column 0, so an `AS` after one can't line up with other aliases, and
        the column aligns on its own.
        """
        return self.SENTINEL_LINE_BREAK in sql.rsplit("\n", 1)[-1]

    # ------------------------------------------------------------------
    # CTE formatting: paren on its own line, comma-prefix separator
    # ------------------------------------------------------------------

    def tablealias_sql(self, expression: exp.TableAlias) -> str:
        alias = self.sql(expression, "this")
        columns = self.expressions(expression, key="columns", flat=True)
        columns_sql = f"({columns})" if columns else ""

        if columns_sql and not self.SUPPORTS_TABLE_ALIAS_COLUMNS:
            columns_sql = ""
            self.unsupported("Named columns are not supported in table alias.")

        if not alias and not self.dialect.UNNEST_COLUMN_ONLY:
            alias = self._next_name()

        # Space before column list only in CTE context: "cte_name (col1, col2)"
        # Table function aliases like UNNEST keep no space: "t(col)"
        sep = " " if isinstance(expression.parent, exp.CTE) else ""
        return f"{alias}{sep}{columns_sql}" if alias and columns_sql else f"{alias}{columns_sql}"

    def unnest_sql(self, expression: exp.Unnest) -> str:
        """Override to omit AS before UNNEST function aliases.

        sqlglot's base Generator.unnest_sql hardcodes " AS {alias}"; this
        override drops the keyword to match jarify's table-alias convention.
        """
        args = self.expressions(expression, flat=True)
        alias = expression.args.get("alias")
        offset = expression.args.get("offset")

        if self.UNNEST_WITH_ORDINALITY and alias and isinstance(offset, exp.Expr):
            alias.append("columns", offset)

        alias_str = f" {self.sql(alias)}" if alias else ""

        if self.UNNEST_WITH_ORDINALITY:
            suffix = f" WITH ORDINALITY{alias_str}" if offset else alias_str
        else:
            if isinstance(offset, exp.Expr):
                suffix = f"{alias_str} WITH OFFSET AS {self.sql(offset)}"
            elif offset:
                suffix = f"{alias_str} WITH OFFSET"
            else:
                suffix = alias_str

        return f"UNNEST({args}){suffix}"

    def cte_sql(self, expression: exp.CTE) -> str:
        prefix, body = self._cte_sql_parts(expression)
        return f"{prefix}\n{body}" if prefix else body

    def _cte_sql_parts(self, expression: exp.CTE) -> tuple[str, str]:
        """Return ``(comment_lines, definition)``; the comment lines go above the CTE."""
        # sqlglot attaches leading comments to the TableAlias child, not the
        # CTE node itself, so both are written here, and neither node writes
        # them again.  They stay on the nodes for a CTE rendered twice, as in
        # a subquery measured for alias alignment.  Leading comments (own-line
        # before the CTE name) are prepended as separate lines; trailing
        # comments stay inline after AS.
        alias_node = expression.args.get("alias")
        comments = [*(expression.comments or []), *((alias_node.comments if alias_node else None) or [])]
        alias_sql = self.sql(alias_node, comment=False) if alias_node else ""

        # A comment written between AS and the opening paren goes after AS,
        # even one that sat on its own line there. It was written last, so it
        # also comes last when several comments go above the CTE.
        after_as = expression.meta.get(CTE_COMMENTS_AFTER_AS) or []

        # Comments on their own line before the `)` that closes the body stay
        # at the end of the body.
        body_end = [c for c in comments if c.strip() in self._closing_paren_comment_texts and c not in after_as]
        comments = [c for c in comments if c not in body_end]
        comments = [c for c in comments if c not in after_as] + [c for c in comments if c in after_as]
        if self._leading_comment_texts:
            lead = [c for c in comments if c.strip() in self._leading_comment_texts and c not in after_as]
            trail = [c for c in comments if c.strip() not in self._leading_comment_texts or c in after_as]
        else:
            lead, trail = [], comments

        trail = [c for c in trail if c.strip()]
        if len(trail) > 1:
            # Only one `--` comment fits after AS, since it ends the line.
            # Several comments go above the CTE instead, one per line, where
            # own-line comments above a CTE are kept.
            lead, trail = [c for c in comments if c.strip()], []
        comment_suffix = self._render_comments(trail)

        materialized = expression.args.get("materialized")
        if materialized is True:
            materialized_str = " MATERIALIZED"
        elif materialized is False:
            materialized_str = " NOT MATERIALIZED"
        else:
            materialized_str = ""

        body = f"{alias_sql} AS{materialized_str}{comment_suffix}\n{self._cte_body_sql(expression, body_end)}"

        return self._render_comments(lead, leading=True), body

    def _cte_body_sql(self, expression: exp.CTE, end_comments: list[str]) -> str:
        """Return the CTE's body in parentheses, with *end_comments* on their own
        lines after its last clause, before the ``)``."""
        if not end_comments:
            return self.wrap(expression)
        return self._wrap_with_end_comments(expression, end_comments)

    def wrap(self, expression: exp.Expr | str) -> str:
        # A comment on its own line before a subquery's closing paren stays at
        # the end of the body, as in a CTE.
        end_comments = keyword_comments(expression, ")") if isinstance(expression, exp.Subquery) else []
        if not end_comments:
            return super().wrap(expression)
        return self._wrap_with_end_comments(expression, end_comments)

    def _wrap_with_end_comments(self, expression: exp.Expr, end_comments: list[str]) -> str:
        """Return *expression*'s body in parentheses, with *end_comments* on their
        own lines after its last clause, before the ``)``."""
        body = "\n".join([self.sql(expression, "this"), *self._own_line_comments(end_comments)])
        return f"(\n{self.indent(body, level=1, pad=0)}\n)"

    def with_sql(self, expression: exp.With) -> str:
        ctes = expression.expressions
        if not ctes:
            return ""
        recursive = "RECURSIVE " if self.CTE_RECURSIVE_KEYWORD_REQUIRED and expression.args.get("recursive") else ""

        def _entry(cte: exp.CTE, sep: str) -> str:
            # Comment lines above a CTE must appear before the separator
            prefix, body = self._cte_sql_parts(cte)
            return f"{prefix}\n{sep}{body}" if prefix else sep + body

        parts = [_entry(ctes[0], f"WITH {recursive}")]
        for cte in ctes[1:]:
            parts.append(_entry(cte, ","))
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # JOIN normalization: bare JOIN → INNER JOIN; LEFT/RIGHT OUTER → LEFT/RIGHT
    # (or LEFT/RIGHT → LEFT/RIGHT OUTER with explicit_outer_join)
    # ------------------------------------------------------------------

    def _normalize_bare_join(self, expression: exp.Join) -> exp.Join:
        """Write a bare JOIN that has an ON or USING condition as INNER JOIN,
        unless normalize_join is off."""
        has_condition = expression.args.get("on") or expression.args.get("using")
        if not self._config.normalize_join:
            return expression
        if expression.side or expression.kind or expression.method or not has_condition:
            return expression
        normalized = expression.copy()
        normalized.set("kind", "INNER")
        return normalized

    def _normalize_outer_keyword(self, expression: exp.Join) -> exp.Join:
        """Drop OUTER from LEFT/RIGHT joins, or add it when explicit_outer_join is set.

        Covers ASOF and NATURAL variants (ASOF LEFT JOIN, NATURAL LEFT JOIN).
        FULL joins keep whatever the input wrote.
        """
        if expression.side not in ("LEFT", "RIGHT") or expression.kind not in ("", "OUTER"):
            return expression
        kind = "OUTER" if self._config.explicit_outer_join else ""
        if expression.kind == kind:
            return expression
        normalized = expression.copy()
        normalized.set("kind", kind or None)
        return normalized

    def join_sql(self, expression: exp.Join) -> str:
        if self.pretty:
            # The first ON condition shares the JOIN line, so a comment written
            # on its own line before it goes above the JOIN. Hoist it before
            # the keyword normalization below copies the node.
            self._hoist_leading_comments(expression.args.get("on"), expression)
        has_condition = expression.args.get("on") or expression.args.get("using")
        if not expression.side and not expression.kind and not expression.method:
            if has_condition:
                # Bare JOIN with a condition — normalize to INNER JOIN
                expression = self._normalize_bare_join(expression)
            else:
                # Comma join (no condition) — delegate to DuckDB's renderer,
                # which emits comma-separated syntax instead of a bare JOIN keyword
                return super().join_sql(expression)
        else:
            expression = self._normalize_outer_keyword(expression)

        if not self.pretty:
            return super().join_sql(expression)

        op_sql = self._join_keyword(expression)
        this = expression.this

        condition_follows = bool(expression.args.get("on") or expression.args.get("using"))

        if self._join_alias_col is not None and isinstance(this, exp.Table):
            table_ref = self.table_parts(this)
            alias_str = self._table_alias_str(this, comment=False)
            table_comments = self._table_comments_sql(this, sql_follows=condition_follows)
            if alias_str:
                pad = " " * max(
                    1, self._join_alias_col - len(op_sql) - 1 - len(table_ref) - self._table_alias_width(this)
                )
                return self.seg(
                    self._inline_on_sql(expression, f"{op_sql} {table_ref}{pad}{alias_str}{table_comments}")
                )
            return self.seg(self._inline_on_sql(expression, f"{op_sql} {table_ref}{table_comments}"))

        if self._join_alias_col is not None and isinstance(this, exp.Unnest):
            alias_node = this.args.get("alias")
            if alias_node:
                full_alias = self.sql(alias_node)  # e.g. "gbv(group_by_value)"
                name_node = alias_node.args.get("this")
                alias_name = self.sql(name_node) if name_node else full_alias
                unnest_no_alias = this.copy()
                unnest_no_alias.set("alias", None)
                unnest_ref = self.sql(unnest_no_alias)
                # Measure by alias name only (end-alignment: alias name ends at
                # _join_alias_col; column definitions extend past that column).
                pad = " " * max(1, self._join_alias_col - len(op_sql) - 1 - len(unnest_ref) - len(alias_name))
                return self.seg(self._inline_on_sql(expression, f"{op_sql} {unnest_ref}{pad}{full_alias}"))

        # No alignment path: render table ref, drop AS for simple tables
        if isinstance(this, exp.Table):
            table_ref = self.table_parts(this)
            alias_str = self._table_alias_str(this, comment=False)
            this_sql = f"{table_ref} {alias_str}" if alias_str else table_ref
            this_sql += self._table_comments_sql(this, sql_follows=condition_follows)
        else:
            this_sql = self.sql(this)

        exprs = self.expressions(expression)
        if exprs:
            this_sql = f"{this_sql},{self.seg(exprs)}"

        return self.seg(self._inline_on_sql(expression, f"{op_sql} {this_sql}"))

    def table_sql(self, expression: exp.Table, sep: str = " AS ") -> str:
        joins = expression.args.get("joins")
        if not (self.pretty and joins):
            return super().table_sql(expression, sep)
        # The first table of a parenthesized join, `(u JOIN v ON …)`. Lay
        # the group out like a FROM clause: the table on its own line, each
        # join on its own line under it, and their aliases aligned.
        first = expression.copy()
        first.set("joins", None)
        saved_align = self._join_alias_col
        self._join_alias_col = self._join_block_align_width(first, joins, -1)
        try:
            table_ref = self.table_parts(first)
            alias_str = self._table_alias_str(first, comment=False)
            if alias_str and self._join_alias_col is not None:
                pad = " " * max(1, self._join_alias_col - len(table_ref) - self._table_alias_width(first))
                head = f"{table_ref}{pad}{alias_str}"
            else:
                head = f"{table_ref} {alias_str}" if alias_str else table_ref
            return head + self._table_comments_sql(first) + "".join(self.sql(join) for join in joins)
        finally:
            self._join_alias_col = saved_align

    def from_sql(self, expression: exp.From) -> str:
        table = expression.this
        if not self.pretty:
            return super().from_sql(expression)

        if isinstance(table, exp.Subquery):
            if self._may_go_on_one_line(table):
                # Render compactly; non-pretty seg() prepends a space, so strip it.
                compact = self._compact_sql(expression).strip()
                if not self.too_wide([compact]):
                    return self.seg(compact)
            return super().from_sql(expression)

        if not isinstance(table, exp.Table):
            return super().from_sql(expression)

        alias_str = self._table_alias_str(table, comment=False)
        if not alias_str:
            return super().from_sql(expression)

        table_ref = self.table_parts(table)
        table_comments = self._table_comments_sql(table)
        if self._join_alias_col is not None:
            pad = " " * max(1, self._join_alias_col - len("FROM") - 1 - len(table_ref) - self._table_alias_width(table))
            return self.seg(f"FROM {table_ref}{pad}{alias_str}{table_comments}")
        return self.seg(f"FROM {table_ref} {alias_str}{table_comments}")

    # ------------------------------------------------------------------
    # FROM/JOIN alignment helpers
    # ------------------------------------------------------------------

    def _join_keyword(self, expression: exp.Join) -> str:
        """Return the join keyword string, e.g. 'LEFT JOIN', 'INNER JOIN'."""
        side = expression.side
        kind = expression.kind
        method = expression.method
        if not self.SEMI_ANTI_JOIN_WITH_SIDE and kind in ("SEMI", "ANTI"):
            side = None
        op = " ".join(part for part in (method, side, kind) if part)
        return f"{op} JOIN" if op else "JOIN"

    def _table_alias_str(self, table: exp.Table, *, comment: bool = True) -> str:
        """Return the alias string for a table node, or empty string if none."""
        alias_node = table.args.get("alias")
        return self.sql(alias_node, comment=comment) if alias_node else ""

    def _table_comments_sql(self, table: exp.Table, *, sql_follows: bool = False) -> str:
        """Render the comments on a table reference and on its alias, after the alias.

        table_parts() renders only the table's name, so the comments sqlglot
        attaches to the table node itself (``JOIN u /* note */ ON``) were lost.
        generate() writes a comment as ``/* */`` when SQL follows it on the
        line. Several comments each get a line, except before a JOIN's ``ON``
        or ``USING``: a comment on its own line there would be lost on the
        next pass, so they stay on the line as ``/* */``.
        """
        alias_node = table.args.get("alias")
        alias_comments = (alias_node.comments if alias_node else None) or []
        comments = [c for c in [*(table.comments or []), *alias_comments] if c.strip()]
        if sql_follows and len(comments) > 1 and not any("*/" in c for c in comments):
            return "".join(f" /*{_mark_comment_lines(c)}*/" if "\n" in c else f" /* {c.strip()} */" for c in comments)
        return self._render_comments(comments)

    def _table_alias_width(self, table: exp.Table) -> int:
        """Return the alias's width for alignment: without its comments, which
        follow the alias on the line."""
        return len(self._table_alias_str(table, comment=False))

    def _inline_on_sql(self, expression: exp.Join, head: str) -> str:
        """Append the ON or USING clause to the JOIN line *head*.

        The ON condition stays inline on one line. A commented condition
        cannot (a ``--`` comment would swallow the rest of the line), and
        neither can one holding a CASE, which is always multi-line. Either is
        laid out like WHERE: AND/OR on their own lines, right-justified so the
        conditions align after ``ON``.
        """
        on_expr = expression.args.get("on")
        using = expression.args.get("using")
        if on_expr:
            if self._has_comments(on_expr) or self._holds_case(on_expr):
                return "\n".join(self._aligned_condition_lines(f"{head} ON", on_expr))
            saved = self.pretty
            self.pretty = False
            try:
                on_rendered = self.sql(on_expr)
            finally:
                self.pretty = saved
            return f"{head} ON {on_rendered}"
        if using:
            cols = ", ".join(self.sql(col) for col in using)
            return f"{head} USING ({cols})"
        return head

    def _entry_alias_str(self, table_expr: exp.Expr) -> str:
        """Return the rendered alias string for a FROM/JOIN entry (Table or Unnest)."""
        if isinstance(table_expr, exp.Table):
            return self._table_alias_str(table_expr)
        if isinstance(table_expr, exp.Unnest):
            alias_node = table_expr.args.get("alias")
            return self.sql(alias_node) if alias_node else ""
        return ""

    def _table_ref_only_sql(self, table_expr: exp.Expr) -> str | None:
        """Return the table reference string (no alias) for simple tables and
        table-function calls (e.g. UNNEST), else None.

        For UNNEST the alias is stripped before rendering so only the function
        call itself is measured.
        """
        if isinstance(table_expr, exp.Table):
            ref = self.table_parts(table_expr)
            return None if "\n" in ref else ref
        if isinstance(table_expr, exp.Unnest):
            stripped = table_expr.copy()
            stripped.set("alias", None)
            ref = self.sql(stripped)
            return None if "\n" in ref else ref
        return None

    def _compute_join_align_width(self, expression: exp.Select) -> int | None:
        """Compute the column aliases end at in the FROM/JOIN block.

        Returns `max(kw_len + 1 + ref_len + alias_len) + 1` across all aliased
        entries so that every alias ENDS at the same column (right-aligned),
        leaving at least one space before the longest entry's alias.
        Returns None when alignment should be skipped (any entry uses a
        subquery, or no entries have aliases).
        """
        from_expr = expression.args.get("from_")
        if not from_expr:
            return None
        return self._join_block_align_width(from_expr.this, expression.args.get("joins") or [], len("FROM"))

    def _join_block_align_width(self, first: exp.Expr, joins: list[exp.Join], first_kw_len: int) -> int | None:
        """Compute the alias column for a first table and its joins.

        *first_kw_len* is the width of the keyword before the first table
        (``FROM``), or ``-1`` when it starts its line, as the first table of a
        parenthesized join does.
        """
        entries: list[tuple[int, str, exp.Expr]] = []

        from_ref = self._table_ref_only_sql(first)
        if from_ref is None:
            return None
        entries.append((first_kw_len, from_ref, first))

        for join in joins:
            # Normalize the keyword before measuring its length so the alignment
            # width matches what join_sql actually renders.  For example,
            # LEFT OUTER JOIN (15 chars) is rendered as LEFT JOIN (9 chars), or
            # LEFT JOIN as LEFT OUTER JOIN when explicit_outer_join is set, and a
            # bare JOIN (4 chars) as INNER JOIN (10 chars), so we must use the
            # post-normalization keyword here.
            kw = self._join_keyword(self._normalize_outer_keyword(self._normalize_bare_join(join)))
            ref = self._table_ref_only_sql(join.this)
            if ref is None:
                return None
            entries.append((len(kw), ref, join.this))

        max_total = 0
        has_alias = False
        for kw_len, ref, table_expr in entries:
            if isinstance(table_expr, exp.Table):
                alias = self._table_alias_str(table_expr)
                if alias:
                    has_alias = True
                    max_total = max(max_total, kw_len + 1 + len(ref) + self._table_alias_width(table_expr))
            elif isinstance(table_expr, exp.Unnest):
                alias_node = table_expr.args.get("alias")
                if alias_node:
                    # Measure by alias name only (e.g. "gbv" not "gbv(col)") so
                    # column definitions don't inflate the alignment width.
                    name_node = alias_node.args.get("this")
                    alias_name = self.sql(name_node) if name_node else ""
                    if alias_name:
                        has_alias = True
                        max_total = max(max_total, kw_len + 1 + len(ref) + len(alias_name))

        if not has_alias:
            return None

        return max_total + 1  # +1 for minimum one space before ON/EOL

    # ------------------------------------------------------------------
    # Connector: break AND/OR onto separate lines in pretty mode only when
    # the compact (single-line) form exceeds max_line_length.  When
    # _connector_force_expand is True (set by WHERE/HAVING rendering) the
    # multi-line form is always used so that _inline_clause_sql can
    # right-justify the operators.
    # ------------------------------------------------------------------

    def connector_sql(
        self,
        expression: exp.Connector,
        op: str,
        stack: list[str | exp.Expr] | None = None,
    ) -> str:
        if stack is not None:
            return super().connector_sql(expression, op, stack)

        # Check for comments before flattening: rendering the terms pops a
        # Paren's comments, so checking afterwards would miss them.
        has_comments = self._has_comments(expression)
        terms: list[str] = []
        ops: list[str] = []
        op_comments: list[list[str]] = []
        self._flatten_connector(expression, terms, ops, op_comments)

        if not terms:
            return super().connector_sql(expression, op)

        if self.pretty:
            if not self._connector_force_expand and not has_comments:
                compact_parts = [terms[0]]
                for connector_op, term in zip(ops, terms[1:], strict=False):
                    compact_parts.append(f"{connector_op} {term}")
                compact = " ".join(compact_parts)
                if not self.too_wide([compact]):
                    return compact
            lines = [terms[0]]
            for connector_op, comments, term in zip(ops, op_comments, terms[1:], strict=False):
                # Comments sqlglot attached to the AND/OR itself go on their own
                # line(s) before it, so they never comment out the connector.
                lines.extend(self._own_line_comments(comments))
                lines.append(f"{connector_op} {term}")
            return "\n".join(lines)

        return f" {op} ".join(terms)

    def _flatten_connector(
        self,
        node: exp.Expr,
        terms: list[str],
        ops: list[str],
        op_comments: list[list[str]] | None = None,
    ) -> None:
        """Recursively flatten a nested AND/OR chain into a flat list.

        When *op_comments* is given, it receives the comments attached to each
        connector, parallel to *ops*.
        """
        if isinstance(node, exp.Connector):
            op_name = "AND" if isinstance(node, exp.And) else "OR"
            self._flatten_connector(node.left, terms, ops, op_comments)
            ops.append(op_name)
            if op_comments is not None:
                if self.pretty and not self._is_select_item(node):
                    # A comment on its own line after the connector goes above it.
                    self._hoist_leading_comments(node.right, node)
                op_comments.append(node.comments or [])
            self._flatten_connector(node.right, terms, ops, op_comments)
        else:
            terms.append(self.sql(node))

    @staticmethod
    def _is_select_item(node: exp.Expr) -> bool:
        """True when *node* is a SELECT-list item, bare or under its alias.

        expressions() renders such an item's own comments itself, and sqlglot
        moves them onto the alias when it parses the output again, so comments
        moved onto the item would not come back in the same place.
        """
        parent = node.parent
        return isinstance(parent, exp.Alias) or (isinstance(parent, exp.Select) and node.arg_key == "expressions")

    def _own_line_comments(self, comments: list[str]) -> list[str]:
        """Render comments as lines that stand on their own, one per comment."""
        rendered = self._render_comments(comments, leading=True)
        return rendered.split("\n") if rendered else []

    @staticmethod
    def _is_comment_line(line: str) -> bool:
        return line.lstrip().startswith(("--", "/*"))

    def _prefix_lines(self, lines: list[str], prefixes: list[str]) -> list[str]:
        """Prepend each line's prefix; an own-line comment takes the prefix of
        the line it precedes, so it lines up with the AND/OR it documents."""
        result: list[str] = []
        for i, line in enumerate(lines):
            anchor = i
            while anchor < len(lines) - 1 and self._is_comment_line(lines[anchor]):
                anchor += 1
            result.append(f"{prefixes[anchor]}{line}")
        return result

    @staticmethod
    def _code_part(line: str) -> str:
        """Return *line* without its trailing ``--`` comment (ignoring ``--`` in quotes)."""
        quote = ""
        for i, char in enumerate(line):
            if quote:
                if char == quote:
                    quote = ""
            elif char in "'\"":
                quote = char
            elif line.startswith("--", i):
                return line[:i]
        return line

    # ------------------------------------------------------------------
    # Paren: keep inline when the content fits within max_line_length
    # ------------------------------------------------------------------

    def paren_sql(self, expression: exp.Paren) -> str:
        if not self.pretty:
            return super().paren_sql(expression)

        comments = expression.pop_comments() or []
        lead = [c for c in comments if c.strip() in self._leading_comment_texts]
        trail = [c for c in comments if c.strip() not in self._leading_comment_texts]

        this = expression.this
        compact = self._compact_sql(this)
        if isinstance(this, exp.Case) and not self._has_comments(this):
            # A CASE is always multi-line. The parentheses stay around it, and
            # it is laid out under its keyword: `(CASE` … `END)`.
            sql = f"({self.sql(expression, 'this')})"
        elif not self._has_comments(this) and not self._holds_case(this) and not self.too_wide([f"({compact})"]):
            sql = f"({compact})"
        else:
            # A comment on its own line before the first condition inside the
            # parentheses stays on its own line, after the "(". It documents
            # that first branch, so AND / OR still break onto their own lines.
            prev_force = self._connector_force_expand
            with self._leading_comments_lifted(expression.this) as inner_lead:
                self._connector_force_expand = prev_force or bool(inner_lead)
                try:
                    inner = self.sql(expression, "this")
                finally:
                    self._connector_force_expand = prev_force
            inner = "\n".join([*self._own_line_comments(inner_lead), inner])
            sql = f"({self.seg(self.indent(inner), sep='')}{self.seg(')', sep='')}"

        inline = self._render_comments(trail) if trail else ""
        if lead:
            rendered_lead = self._render_comments(lead, leading=True)
            return f"{rendered_lead}\n{sql}{inline}" if rendered_lead else f"{sql}{inline}"
        return f"{sql}{inline}"

    # ------------------------------------------------------------------
    # IF(): render exp.If as the DuckDB IF() function (not CASE WHEN)
    # ------------------------------------------------------------------

    def if_sql(self, expression: exp.If) -> str:
        """Render exp.If as DuckDB's IF(cond, then[, else]) function call.

        In non-pretty mode, delegates to the generic func() helper.

        In pretty mode, all arguments are rendered through _compact_sql so
        that boolean conditions (AND / OR chains) cannot wrap mid-argument.

        When the compact single-line form fits within max_line_length it is
        used as-is. When it is too wide the call expands using a leading-
        comma outer form like SELECT column lists (content at pad+1, comma
        at pad). The condition stays compact on one line, but true/false
        branches may use their normal multi-line formatting when still too
        wide. An argument that carries a comment or holds a CASE always
        expands the call and keeps its normal multi-line formatting.
        """
        has_else = expression.args.get("false") is not None

        if not self.pretty:
            if has_else:
                return self.func("IF", expression.this, expression.args["true"], expression.args["false"])
            return self.func("IF", expression.this, expression.args["true"])

        # Pretty mode: keep the condition compact so AND/OR chains do not
        # wrap mid-call. Branches start compact too, but can fall back to
        # their normal SQL rendering when still too wide on their own.
        args = [a for a in (expression.this, expression.args["true"], expression.args.get("false")) if a is not None]
        compact_args = [self._compact_sql(a) for a in args]

        # A commented argument can't be rendered compactly (a -- comment would
        # swallow the rest of the line), and neither can one holding a CASE,
        # which is always multi-line. Either forces the expanded form and
        # keeps its normal multi-line rendering.
        own_sqls = [self._multiline_arg_sql(a) for a in args]

        func_name = self.normalize_func("if")
        inline = f"{func_name}({', '.join(compact_args)})"
        if all(own is None for own in own_sqls) and not self.too_wide([inline]):
            return inline

        branch_sqls = [own_sqls[0] if own_sqls[0] is not None else compact_args[0]]
        for arg, compact, own in zip(args[1:], compact_args[1:], own_sqls[1:], strict=True):
            if own is not None:
                branch_sqls.append(own)
            else:
                branch_sqls.append(compact if not self.too_wide([compact]) else self.sql(arg))

        # Too wide: expand the outer IF() with leading commas. Keep the
        # condition on one compact line, but allow branch expressions to bring
        # along their own nested wrapping.
        p = self.pad

        def _prefixed(arg_sql: str, *, first: str) -> list[str]:
            # A multi-line argument continues from the argument's first
            # column. (_anchor_cases() lines a CASE up under its keyword.)
            lines = arg_sql.splitlines() or [arg_sql]
            rest = " " * (p + 2)
            return [f"{first}{lines[0]}", *(f"{rest}{line}" for line in lines[1:])]

        lines = [f"{func_name}("]
        lines.extend(_prefixed(branch_sqls[0], first=" " * (p + 2)))
        for arg_sql in branch_sqls[1:]:
            lines.extend(_prefixed(arg_sql, first=" " * (p + 1) + ","))
        lines.append(")")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # CASE: simple CASE keeps WHEN/THEN on one line; searched CASE puts
    # THEN on its own line and expands AND/OR conditions inside WHEN.
    # ------------------------------------------------------------------

    def case_sql(self, expression: exp.Case) -> str:
        this = self.sql(expression, "this")

        def _branch_sql(node: exp.Expr, keyword: str) -> str:
            """A branch value stays on one line when it fits, unless it holds a CASE
            or its one-line form still breaks lines, as a subquery holding a WITH does."""
            compact = self._compact_sql(node)
            if self._holds_case(node) or "\n" in compact or self.too_wide([f"{keyword} {compact}"]):
                return self.sql(node)
            return compact

        when_parts: list[str] = []
        then_parts: list[str] = []
        for e in expression.args["ifs"]:
            wp_expr = e.args.get("this")
            if self.pretty and not this and wp_expr is not None:
                prev_force = self._connector_force_expand
                self._connector_force_expand = True
                try:
                    wp = self.sql(wp_expr)
                finally:
                    self._connector_force_expand = prev_force
            elif self.pretty and wp_expr is not None and self._holds_case(wp_expr):
                wp = self.sql(wp_expr)
            else:
                wp = self._compact_sql(wp_expr) if wp_expr is not None else self.sql(e, "this")

            true_expr = e.args.get("true")
            tp = _branch_sql(true_expr, "THEN") if self.pretty and true_expr is not None else self.sql(e, "true")
            when_parts.append(wp)
            then_parts.append(tp)

        default_expr = expression.args.get("default")
        default_sql: str | None = None
        if default_expr is not None:
            default_sql = _branch_sql(default_expr, "ELSE") if self.pretty else self.sql(expression, "default")

        # Comments on WHEN, THEN and ELSE go on their own lines above the line
        # their keyword is on, as comments on AND / OR go above the connector.
        # On one line, they follow their keyword.
        branches = expression.args["ifs"]
        when_comments = [keyword_comments(e, "WHEN") for e in branches]
        then_comments = [keyword_comments(e, "THEN") for e in branches]
        else_comments = keyword_comments(expression, "ELSE")

        def _keyword(keyword: str, comments: list[str]) -> str:
            return f"{keyword}{self._comments_before_sql(comments)}" if not self.pretty else keyword

        def _append_multiline(
            stmts: list[str], keyword: str, value: str, *, prefix: str = "", continuation_prefix: str = ""
        ) -> None:
            lines = value.splitlines()
            stmts.append(f"{prefix}{keyword} {lines[0]}")
            stmts.extend(f"{continuation_prefix}{line}" for line in lines[1:])

        def _comment_lines(comments: list[str], prefix: str = "") -> list[str]:
            return [f"{prefix}{line}" for line in self._own_line_comments(comments)] if self.pretty else []

        def _build_simple(align: bool) -> list[str]:
            max_w = max((len(w) for w in when_parts), default=0) if align else 0
            stmts = [f"CASE {this}" if this else "CASE"]
            for wp, tp, when_c, then_c in zip(when_parts, then_parts, when_comments, then_comments, strict=True):
                stmts.extend(_comment_lines([*when_c, *then_c]))
                stmts.append(f"{_keyword('WHEN', when_c)} {wp.ljust(max_w)} {_keyword('THEN', then_c)} {tp}")
            if default_sql is not None:
                stmts.extend(_comment_lines(else_comments))
                stmts.append(f"{_keyword('ELSE', else_comments)} {default_sql}")
            stmts.append("END")
            return stmts

        def _searched_when_prefixes(continuation: list[str]) -> list[str]:
            # AND / OR are right-aligned; the other lines of the condition
            # after one, such as a wrapped IN list, move right with it.
            prefixes = []
            prefix = "  "
            for line in continuation:
                if line.startswith(("AND ", "OR ")):
                    prefix = "   " if line.startswith("OR ") else "  "
                prefixes.append(prefix)
            return prefixes

        def _build_searched() -> list[str]:
            stmts = ["CASE"]
            for wp, tp, when_c, then_c in zip(when_parts, then_parts, when_comments, then_comments, strict=True):
                wp_lines = wp.splitlines()
                stmts.extend(_comment_lines(when_c, " "))
                stmts.append(f" WHEN {wp_lines[0]}")
                continuation = wp_lines[1:]
                stmts.extend(self._prefix_lines(continuation, _searched_when_prefixes(continuation)))
                stmts.extend(_comment_lines(then_c, " "))
                _append_multiline(stmts, "THEN", tp, prefix=" ", continuation_prefix="  ")
            if default_sql is not None:
                stmts.extend(_comment_lines(else_comments, " "))
                _append_multiline(stmts, "ELSE", default_sql, prefix=" ", continuation_prefix="  ")
            stmts.append(" END")
            return stmts

        if not self.pretty:
            return " ".join(_build_simple(align=False))

        # Mark the C of CASE and the E of END for _anchor_cases(), which moves
        # the lines laid out here to the column the CASE keyword lands in.
        if not this:
            stmts = _build_searched()
            stmts[0] = _CASE_MARK + stmts[0][1:]
            stmts[-1] = f" {_END_MARK}ND"
        else:
            align = len(when_parts) >= 2 and all("\n" not in tp for tp in then_parts)
            stmts = _build_simple(align=align)
            # END goes under the leading comma; with trailing commas there's
            # none, and END goes under CASE.
            stmts[0] = (_SIMPLE_CASE_MARK if self.leading_comma else _CASE_MARK) + stmts[0][1:]
            stmts[-1] = f"{_END_MARK}ND"
        return self.indent("\n".join(stmts), skip_first=True, skip_last=True)

    # ------------------------------------------------------------------
    # WHERE / HAVING: first condition inline, AND/OR right-justified
    # ------------------------------------------------------------------

    def where_sql(self, expression: exp.Where) -> str:
        """Format WHERE with leading-AND style and = operator column-alignment.

        When the top-level condition is a pure AND chain the = signs in simple
        equality conditions are padded so they all align at the same column.
        The target column is max(LHS width across all EQ in WHERE) + 1,
        ensuring exactly one space between the longest LHS and its = sign.

        Parenthesised conditions that are direct AND operands (e.g. compound OR
        filters) are rendered on a single line rather than expanded.

        Falls back to _inline_clause_sql when the top-level is not AND (e.g.
        a bare OR at the top level).
        """
        if self.pretty and isinstance(expression.parent, (exp.Select, exp.Update, exp.Delete)):
            # The first condition shares the WHERE line, so a comment written
            # on its own line before it goes above WHERE. (Not in an aggregate's
            # FILTER (WHERE …), which stays on the aggregate's line.)
            self._hoist_leading_comments(expression.this, expression)
        if not self.pretty or not isinstance(expression.this, exp.And):
            return self._inline_clause_sql("WHERE", expression)

        operands = self._flatten_and(expression.this)
        conditions = [cond for cond, _ in operands]

        # Max EQ LHS width across top-level AND operands only — nested EQs (inside
        # Paren, subqueries, etc.) must not influence padding of sibling conditions.
        # A multi-line LHS, such as a CASE, isn't padded, so it doesn't count.
        eq_lhs_sqls = [self.sql(cond.this) for cond in conditions if isinstance(cond, exp.EQ)]
        eq_lhs_widths = [len(lhs) for lhs in eq_lhs_sqls if "\n" not in lhs]
        # Only align when there are at least 2 top-level EQ comparisons
        target = (max(eq_lhs_widths) + 1) if len(eq_lhs_widths) >= 2 else 0

        result: list[str] = []
        for i, (cond, and_comments) in enumerate(operands):
            # Comments attached to the AND before this operand stay on their
            # own line(s), aligned with that AND.
            result.extend(f"  {line}" for line in self._own_line_comments(and_comments))
            if target > 0 and isinstance(cond, exp.EQ):
                lhs = self.sql(cond.this)
                rhs = self.sql(cond.expression)
                cond_str = f"{lhs.ljust(target)}= {rhs}" if "\n" not in lhs else self.sql(cond)
            else:
                cond_str = (
                    self.sql(cond)
                    if isinstance(cond, exp.Paren) and (self._has_comments(cond) or self._holds_case(cond))
                    else self._compact_sql(cond)
                    if isinstance(cond, exp.Paren)
                    else self.sql(cond)
                )

            if i == 0:
                result.append(f"WHERE {cond_str}")
            elif "\n" in cond_str:
                lines = cond_str.splitlines()
                result.append(f"  AND {lines[0]}")
                result.extend(f"  {line}" for line in lines[1:])
            else:
                result.append(f"  AND {cond_str}")

        return self.seg("\n".join(result))

    def _flatten_and(self, condition: exp.Expr, comments: list[str] | None = None) -> list[tuple[exp.Expr, list[str]]]:
        """Return the flat list of operands from a nested AND chain.

        Each operand is paired with the comments attached to the AND that
        precedes it (sqlglot attaches a comment on its own line before ``AND``
        to the And node). The first operand gets *comments*.
        """
        if isinstance(condition, exp.And):
            left = self._flatten_and(condition.this, comments)
            # A comment on its own line after AND goes above it, with the AND's own.
            self._hoist_leading_comments(condition.expression, condition)
            return left + self._flatten_and(condition.expression, condition.comments or [])
        return [(condition, comments or [])]

    # Nodes whose comments come from an operator token after their first operand
    # (``=``, ``AND``, ``IN``, ``BETWEEN``), not from the token that starts them.
    _INFIX_NODES: ClassVar[tuple[type[exp.Expr], ...]] = (exp.Binary, exp.In, exp.Between)

    def _first_token_nodes(self, condition: exp.Expr) -> list[exp.Expr]:
        """Return the nodes that may hold the comments written before *condition*'s first token.

        sqlglot attaches an own-line comment to the node built from the token
        after it: the column in ``a = 1``, the ``CAST`` in ``CAST(a AS int) = 1``.
        Those nodes render their comments after themselves, inside the
        condition. Walk down the operands that come first, skipping the nodes
        whose comments belong to an operator token.
        """
        nodes: list[exp.Expr] = []
        node: exp.Expr | None = condition
        while node is not None:
            # AND / OR are Funcs too; their comments are the connector's.
            infix = isinstance(node, exp.Connector) or (
                isinstance(node, self._INFIX_NODES) and not isinstance(node, exp.Func)
            )
            if not infix:
                nodes.append(node)
            starts_with_this = (
                isinstance(node, self._INFIX_NODES)
                or (isinstance(node, exp.Cast) and not isinstance(node, exp.TryCast))  # a::int
                or (isinstance(node, exp.Not) and isinstance(node.this, exp.Is))  # a IS NOT NULL
                or (isinstance(node, exp.Not) and self._negated_after_operand(node.this))  # a NOT IN (…)
            )
            node = node.this if starts_with_this and isinstance(node.this, exp.Expr) else None
        return nodes

    def _detach_leading_comments(
        self, condition: exp.Expr | None
    ) -> tuple[list[str], list[tuple[exp.Expr, list[str]]]]:
        """Detach the own-line comments written before *condition*'s first token.

        Returns the comments, and each node they came from with its original
        comment list, so a caller can put them back.
        """
        lead: list[str] = []
        detached: list[tuple[exp.Expr, list[str]]] = []
        if condition is None or not self._leading_comment_texts:
            return lead, detached
        for node in self._first_token_nodes(condition):
            comments = node.comments or []
            node_lead = [c for c in comments if c.strip() in self._leading_comment_texts]
            if node_lead:
                detached.append((node, comments))
                lead.extend(node_lead)
                node.comments = [c for c in comments if c.strip() not in self._leading_comment_texts]
        return lead, detached

    def _hoist_leading_comments(self, condition: exp.Expr | None, owner: exp.Expr) -> None:
        """Move the own-line comments written before *condition* onto *owner*.

        *owner* renders its comments on their own line(s) before the line that
        starts the condition: a WHERE, HAVING or JOIN renders them above its
        keyword, an AND / OR above the connector. Moving them, rather than
        rendering them here, keeps a node that is rendered twice (once to
        measure it) from losing them.
        """
        lead, _ = self._detach_leading_comments(condition)
        if lead:
            owner.add_comments(lead)

    @contextlib.contextmanager
    def _leading_comments_lifted(self, condition: exp.Expr | None) -> t.Iterator[list[str]]:
        """Detach the own-line comments written before *condition* while the block runs.

        Yields them, for the caller to render on their own line(s) before the
        condition, and puts them back afterwards: a node that is rendered twice
        (once to measure it) must find them again.
        """
        lead, detached = self._detach_leading_comments(condition)
        try:
            yield lead
        finally:
            for node, comments in detached:
                node.comments = comments

    def _has_comments(self, expression: exp.Expr | None) -> bool:
        """Return True when expression or any descendant carries SQL comments."""
        if expression is None:
            return False
        return any(getattr(node, "comments", None) or all_keyword_comments(node) for node in expression.walk())

    def _has_inner_comments(self, expression: exp.Expr) -> bool:
        """Return True when a descendant of expression (not expression itself) carries comments."""
        return any(node.comments or all_keyword_comments(node) for node in expression.walk() if node is not expression)

    def _may_go_on_one_line(self, query: exp.Expr) -> bool:
        """Return True unless *query*, a subquery, must take its multi-line form.

        A commented subquery can't go on one line (a -- comment would swallow
        the rest of it), and neither can one holding a CASE, which is always
        multi-line, or a WITH, whose CTEs are laid out as at the top level.
        """
        return not self._has_comments(query) and not self._holds_case(query) and query.find(exp.With) is None

    def _multiline_arg_sql(self, expression: exp.Expr) -> str | None:
        """Return expression's normal SQL when a call can't put it on one line.

        That is when expression carries a comment, which would swallow the
        rest of a one-line call, or holds a CASE that renders across lines
        (a CASE is always multi-line). Otherwise return None.
        """
        if self._has_comments(expression):
            return self.sql(expression)
        if not self._holds_case(expression):
            return None
        sql = self.sql(expression)
        return sql if "\n" in sql else None

    @staticmethod
    def _holds_case(expression: exp.Expr | None) -> bool:
        """Return True when expression is or contains a CASE, which is always multi-line."""
        return expression is not None and expression.find(exp.Case) is not None

    def _compact_sql(self, expression: exp.Expr) -> str:
        """Render expression compactly without line breaks."""
        saved = self.pretty
        self.pretty = False
        try:
            result = self.sql(expression)
        finally:
            self.pretty = saved
        return result

    def having_sql(self, expression: exp.Having) -> str:
        if self.pretty:
            # Like WHERE: a comment before the first condition goes above HAVING.
            self._hoist_leading_comments(expression.this, expression)
        return self._inline_clause_sql("HAVING", expression)

    def qualify_sql(self, expression: exp.Qualify) -> str:
        """Render QUALIFY with its condition on the next line, as sqlglot does.

        A comment written on its own line before the condition stays there,
        between QUALIFY and the condition. A comment on or above the QUALIFY
        line goes above QUALIFY (see WITH_SEPARATED_COMMENTS), as for WHERE.
        """
        if not self.pretty:
            return super().qualify_sql(expression)
        with self._leading_comments_lifted(expression.this) as lead:
            this = self.sql(expression, "this")
        body = "\n".join([*self._own_line_comments(lead), this])
        return f"{self.seg('QUALIFY')}{self.sep()}{self.indent(body)}"

    def _inline_clause_sql(self, keyword: str, expression: exp.Expr) -> str:
        """Format a clause (WHERE/HAVING) with the first condition inline.

        Places the first condition on the same line as the keyword, then
        right-justifies AND/OR so all condition content aligns at column
        len(keyword) + 1 (e.g. column 6 for WHERE, column 7 for HAVING).

        Lines inside parentheses are indented by self.pad relative to their
        position in the original connector output, preserving the standard
        paren indentation that the rest of the generator uses.
        """
        if not self.pretty:
            this = self.sql(expression, "this")
            return f"{self.seg(keyword)} {this}"

        # For a flat same-type connector chain (pure OR or pure AND, no mixing),
        # try compact first — mirrors paren_sql's inline-if-fits logic.
        # Mixed AND/OR chains and IN-subquery expressions keep their expanded form.
        # Check for comments before flattening: rendering the terms pops a
        # Paren's comments, so a second render would lose them.
        this = expression.this
        if isinstance(this, exp.Connector) and not self._has_comments(this) and not self._holds_case(this):
            terms_temp: list[str] = []
            ops_list: list[str] = []
            self._flatten_connector(this, terms_temp, ops_list)
            if len(set(ops_list)) <= 1:
                compact = self._compact_sql(this)
                if not self.too_wide([f"{keyword} {compact}"]):
                    return self.seg(f"{keyword} {compact}")

        return self.seg("\n".join(self._aligned_condition_lines(keyword, this)))

    def _aligned_condition_lines(self, keyword: str, condition: exp.Expr) -> list[str]:
        """Render *condition* after *keyword* with AND/OR right-justified.

        The first line starts with the keyword; top-level AND/OR lines are
        right-justified so condition content aligns one column after the
        keyword's last line (e.g. column 6 for WHERE, column 7 for HAVING).
        The other lines of a condition, such as a wrapped ``IN (…)`` list's
        values and ``)``, keep their indentation relative to the line the
        condition starts on: they move right with its AND/OR. An own-line
        comment lines up with the line it precedes.
        """
        # Force connector_sql to produce multi-line output (for post-processing
        # below) even if the compact form would fit within max_line_length.
        prev_force = self._connector_force_expand
        self._connector_force_expand = True
        try:
            lines = self.sql(condition).split("\n")
        finally:
            self._connector_force_expand = prev_force

        keyword_width = len(keyword.rsplit("\n", 1)[-1]) + 1  # e.g. 6 for "WHERE "
        prefixes: list[str] = []
        first_code = self._code_part(lines[0])
        depth = first_code.count("(") - first_code.count(")")
        # The first condition's lines start at the keyword's column.
        condition_prefix = ""

        for line in lines[1:]:
            if depth == 0 and line.startswith(("AND ", "OR ")):
                connector_width = len(line.split(" ", 1)[0]) + 1
                condition_prefix = " " * max(0, keyword_width - connector_width)
            prefixes.append(condition_prefix)
            if not self._is_comment_line(line):
                code = self._code_part(line)
                depth += code.count("(") - code.count(")")

        return [f"{keyword} {lines[0]}", *self._prefix_lines(lines[1:], prefixes)]

    # ------------------------------------------------------------------
    # IS NOT NULL: preserve original form instead of NOT x IS NULL
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # IN (subquery): opening paren on its own line
    # IN (value, …): one value per line, like wrapped call arguments
    # ------------------------------------------------------------------

    def in_sql(self, expression: exp.In) -> str:
        """Render IN inline when it fits, multiline otherwise.

        When the compact form ``col IN (SELECT ...)`` fits within
        ``max_line_length``, it is kept on a single line.  Only when the
        inline form would exceed the threshold does it fall back to the
        block style::

            col IN
            (
              SELECT ...
            )

        A value list likewise stays inline while ``col IN (a, b)`` fits.
        Otherwise, or when a value carries a comment, the values go one per
        line in leading-comma style, like wrapped call arguments::

            col IN (
               a
              ,b
            )

        Under a NOT, the operator is written ``NOT IN`` (see
        ``_negated_after_operand``).
        """
        if expression.args.get("unnest"):
            return super().in_sql(expression)
        this = self.sql(expression, "this")
        op = "NOT IN" if self._negated_after_operand(expression) else "IN"
        query = expression.args.get("query")
        if self.pretty and query is not None:
            if self._may_go_on_one_line(query):
                compact = self._compact_sql(query.this)
                if not self.too_wide([f"{this} {op} ({compact})"]):
                    return f"{this} {op} ({compact})"
            select_sql = self.sql(query.this)
            indented = self.indent(select_sql)
            return f"{this} {op}\n(\n{indented}\n)"
        field = expression.args.get("field")
        is_global = " GLOBAL" if expression.args.get("is_global") else ""
        if query is not None:
            in_sql = self.sql(query)
        elif field is not None:
            in_sql = self.sql(field)
        else:
            values = self.expressions(expression, dynamic=True, new_line=True, skip_first=True, skip_last=True)
            # The values alone may fit while the whole `col IN (…)` doesn't.
            if self.pretty and not is_global and "\n" not in values and self.too_wide([f"{this} {op} ({values})"]):
                values = self._wrapped_args([self.sql(e) for e in expression.expressions])
            in_sql = f"({values})"
        return f"{this}{is_global} {op} {in_sql}"

    # ------------------------------------------------------------------
    # Star: expand EXCLUDE / REPLACE / RENAME as multi-line select content
    # ------------------------------------------------------------------

    def star_sql(self, expression: exp.Star) -> str:
        except_ = self.expressions(expression, key="except_", flat=True)
        replace = self.expressions(expression, key="replace", flat=True)
        rename = self.expressions(expression, key="rename", flat=True)

        except_sql = f" {self.STAR_EXCEPT} ({except_})" if except_ else ""
        replace_sql = f" REPLACE ({replace})" if replace else ""
        rename_sql = f" RENAME ({rename})" if rename else ""

        inline = f"*{except_sql}{replace_sql}{rename_sql}"
        has_modifiers = bool(except_ or replace or rename)
        if not (self.pretty and has_modifiers):
            return inline if self.pretty and not self.too_wide([inline]) else super().star_sql(expression)

        lines = ["*"]
        for keyword, key in ((self.STAR_EXCEPT, "except_"), ("REPLACE", "replace"), ("RENAME", "rename")):
            saved_align = self._as_align_width
            payload_expressions = list(expression.args.get(key) or [])
            if key in ("replace", "rename"):
                prefix_width = self._star_list_prefix_width(expression)
                self._as_align_width = self._snap_to_alias_guide(
                    self._compute_as_align_width(payload_expressions, prefix_width=prefix_width),
                    prefix_width=prefix_width,
                )
            try:
                payload = self.expressions(expression, key=key, indent=False)
            finally:
                self._as_align_width = saved_align
            if not payload:
                continue
            if key in ("replace", "rename"):
                payload = self._mark_alias_list(expression, payload)
            lines.append(f" {keyword} (")
            lines.extend(f"   {line}" for line in payload.splitlines())
            lines.append(" )")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Inequality operator: always emit != (never <>)
    # ------------------------------------------------------------------

    def neq_sql(self, expression: exp.NEQ) -> str:
        return self.binary(expression, "!=")

    # IS NOT NULL: preserve original form instead of NOT x IS NULL
    # NOT IN / NOT BETWEEN / NOT SIMILAR TO / NOT GLOB: NOT after the operand
    # ------------------------------------------------------------------

    def not_sql(self, expression: exp.Not) -> str:
        inner = expression.this
        # Comments written after NOT stay after it.
        after_not = keyword_comments(expression, "NOT")
        if isinstance(inner, exp.Is) and isinstance(inner.expression, exp.Null):
            # A trailing comment after NULL is attached to the Null node, which
            # this shortcut never renders, so carry its comments over. NOT
            # moves after the column, so its comments go at the end too.
            comments = [*after_not, *(inner.comments or []), *(inner.expression.comments or [])]
            return self.maybe_comment(f"{self.sql(inner.this)} IS NOT NULL", comments=comments)
        if self._negated_after_operand(inner):
            # The predicate writes the NOT itself, after its operand, so the
            # comments written after NOT go at the end, as for IS NOT NULL.
            return self.maybe_comment(self.sql(expression, "this"), comments=after_not)
        return f"NOT{self._comments_before_sql(after_not)} {self.sql(expression, 'this')}"

    def _comments_before_sql(self, comments: list[str]) -> str:
        """Render comments that SQL follows on their line, each as `` /* … */``.

        A comment holding ``*/`` can't be a block comment, so it keeps ``--``
        and ends its line instead of commenting out the SQL after it.
        """
        parts = []
        for comment in comments:
            if "\n" in comment:
                parts.append(f" /*{_mark_comment_lines(comment)}*/")
            elif "*/" in comment:
                parts.append(f" -- {comment.strip()}\n")
            elif comment.strip():
                parts.append(f" /* {comment.strip()} */")
        return "".join(parts)

    @staticmethod
    def _negated_after_operand(expression: exp.Expr | None) -> bool:
        """True when *expression* is a predicate its parent NOT negates as ``x NOT IN (…)``.

        sqlglot parses ``a NOT IN (…)`` and ``NOT a IN (…)`` to the same
        ``Not(In)`` tree, and DuckDB reads both as ``NOT (a IN (…))``. Jarify
        writes the ``NOT`` after the operand, the form ``NOT LIKE`` and
        ``IS NOT NULL`` keep. The same goes for ``NOT BETWEEN``, ``NOT SIMILAR
        TO`` and ``NOT GLOB``. ``NOT (a IN (…))`` keeps its parentheses, so its
        ``NOT`` stays in front. An ``IN UNNEST`` and a ``BETWEEN SYMMETRIC``,
        which DuckDB's generator rewrites, keep the leading ``NOT`` too.
        """
        if expression is None or not isinstance(expression.parent, exp.Not) or expression.arg_key != "this":
            return False
        if isinstance(expression, exp.In):
            return not expression.args.get("unnest")
        if isinstance(expression, exp.Between):
            return not expression.args.get("symmetric")
        return isinstance(expression, (exp.SimilarTo, exp.Glob))

    def between_sql(self, expression: exp.Between) -> str:
        if not self._negated_after_operand(expression):
            return super().between_sql(expression)
        this = self.sql(expression, "this")
        low = self.sql(expression, "low")
        high = self.sql(expression, "high")
        return f"{this} NOT BETWEEN {low} AND {high}"

    def similarto_sql(self, expression: exp.SimilarTo) -> str:
        return self.binary(expression, "NOT SIMILAR TO" if self._negated_after_operand(expression) else "SIMILAR TO")

    def glob_sql(self, expression: exp.Glob) -> str:
        return self.binary(expression, "NOT GLOB" if self._negated_after_operand(expression) else "GLOB")

    # ------------------------------------------------------------------
    # format_args: apply leading-comma style when function args wrap
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # FROM-first: SELECT * FROM t → FROM t
    # ------------------------------------------------------------------

    def select_sql(self, expression: exp.Select) -> str:
        # Compute and store join alias alignment width for this SELECT's FROM/JOIN block
        saved_align = self._join_alias_col
        if self.pretty:
            self._join_alias_col = self._compute_join_align_width(expression)
        try:
            exprs = expression.expressions
            from_ = expression.args.get("from_")

            star = exprs[0] if len(exprs) == 1 and isinstance(exprs[0], exp.Star) else None
            plain_star = star is not None and not any(star.args.get(k) for k in ("except_", "replace", "rename"))

            # Detect VALUES-only CTE body: SELECT * FROM (VALUES ...) AS _values
            # sqlglot parses `WITH t(a,b) AS (VALUES ...)` into this shape; render
            # it back to a plain VALUES block instead of FROM (VALUES ...) AS _values.
            if (
                self.pretty
                and self._config.prefer_from_first
                and plain_star
                and not expression.args.get("distinct")
                and not expression.args.get("joins")
                and isinstance(from_, exp.From)
                and isinstance(from_.this, exp.Values)
            ):
                return self._cte_values_sql(from_.this)

            # FROM-first is safe when there are no explicit joins. Comma joins
            # (kind=None, no on/using) are fine — sqlglot round-trips them
            # correctly. A query written FROM-first with explicit joins
            # (INNER, LEFT, SEMI, etc.) stays FROM-first: parse_sql moves its
            # joins to the query and marks it, so it re-parses the same way.
            # `SELECT * FROM t JOIN u` keeps its SELECT.
            joins = expression.args.get("joins") or []
            only_comma_joins = all(
                not j.args.get("kind")
                and not j.args.get("side")
                and not j.args.get("method")
                and not j.args.get("on")
                and not j.args.get("using")
                for j in joins
            )
            if (
                self.pretty
                and self._config.prefer_from_first
                and plain_star
                and not expression.args.get("distinct")
                and (only_comma_joins or expression.meta.get(FROM_FIRST_JOINS_KEY))
            ):
                expr_copy = expression.copy()
                expr_copy.set("expressions", [])
                sql = super().select_sql(expr_copy)
                if expression.comments and not expr_copy.comments:
                    # After a WITH clause sqlglot writes the comments above the
                    # query and pops them from the copy; pop them here too, or
                    # sql() writes them a second time above the WITH.
                    expression.pop_comments()
                # Strip the bare "SELECT" line (no columns → "SELECT\nFROM ...")
                # Uses multiline ^ so indented "  SELECT" inside CTEs is never matched.
                return re.sub(r"(?m)^SELECT\n", "", sql)
            return super().select_sql(expression)
        finally:
            self._join_alias_col = saved_align

    def _cte_values_sql(self, expression: exp.Values) -> str:
        """Render a VALUES block for a CTE body.

        Produces leading-comma row list with column alignment: the first
        column in each row is padded so that the second (and subsequent)
        column values align across all rows.
        """
        rows = expression.expressions  # list of Tuple nodes
        if not rows:
            return "VALUES"

        rendered: list[list[str]] = [[self.sql(cell) for cell in tup.expressions] for tup in rows]

        num_cols = max(len(r) for r in rendered) if rendered else 0
        if num_cols == 0:
            return "VALUES"

        # Max rendered width per non-last column for padding alignment
        col_widths: list[int] = [
            max((len(r[col_idx]) for r in rendered if col_idx < len(r)), default=0) for col_idx in range(num_cols - 1)
        ]

        # Build each row: (val0,<pad>val1,<pad>val2,...,last_val)
        # The comma follows immediately after each non-last value; trailing
        # spaces pad up to max_width+1 so the next value aligns.
        row_sqls: list[str] = []
        for cells in rendered:
            parts: list[str] = []
            for i, cell in enumerate(cells):
                if i < len(col_widths):
                    pad = " " * (col_widths[i] - len(cell) + 1)
                    parts.append(f"{cell},{pad}")
                else:
                    parts.append(cell)
            row_sqls.append(f"({''.join(parts)})")

        # Leading-comma style: first row gets a leading space, rest get comma
        lines = [f" {row_sqls[0]}"]
        lines.extend(f",{row}" for row in row_sqls[1:])

        body = self.indent("\n".join(lines))
        return f"VALUES\n{body}"

    # ------------------------------------------------------------------
    # GROUP BY / ORDER BY ALL: keep ALL inline; otherwise one expression per line
    # ------------------------------------------------------------------

    def group_sql(self, expression: exp.Group) -> str:
        group_by_all = expression.args.get("all")
        if group_by_all is True:
            return self.seg("GROUP BY ALL")
        if self.pretty and expression.expressions:
            # Force multi-line: mirror op_expressions but always flat=False
            modifier = " DISTINCT" if group_by_all is False else ""
            expressions_sql = self.expressions(expression, flat=False)
            return f"{self.seg(f'GROUP BY{modifier}')}{self.sep() if expressions_sql else ''}{expressions_sql}"
        return super().group_sql(expression)

    def order_sql(self, expression: exp.Order, flat: bool = False) -> str:
        if self.pretty and self._is_order_by_all(expression):
            return self.seg("ORDER BY ALL")
        sql = super().order_sql(expression, flat=flat)
        # A CASE never fits on a line: it is always multi-line.
        keys_hold_case = self.pretty and any(self._holds_case(key) for key in expression.expressions)
        this_holds_case = self.pretty and self._holds_case(expression.args.get("this"))
        if not self.pretty or not (self.too_wide([sql]) or keys_hold_case or this_holds_case):
            return sql
        if expression.args.get("this") is not None:
            # An aggregate's `x ORDER BY a, b` is a call argument (calls
            # rendered through func() lay it out in _ordered_aggregate_sql).
            return self._order_below_sql(self.sql(expression, "this"), expression)
        if flat and isinstance(expression.parent, exp.Window):
            return self._argument_lines(self._wrapped_list_clause(self._order_keyword(expression), expression))
        return sql

    @staticmethod
    def _order_keyword(expression: exp.Order) -> str:
        return f"ORDER {'SIBLINGS ' if expression.args.get('siblings') else ''}BY"

    def _order_below_sql(self, arg_sql: str, order: exp.Order) -> str:
        """Return a call argument with an aggregate's ORDER BY on its own line below it.

        The keys stay on the ORDER BY line while it fits and go one per line
        otherwise, like a window's; a CASE, always multi-line, never fits.
        The lines are laid out for one argument of a wrapped call (see
        _argument_lines).
        """
        keyword = self._order_keyword(order)
        clause = f"{keyword} {self.expressions(order, flat=True)}"
        if self.too_wide([clause]) or any(self._holds_case(key) for key in order.expressions):
            clause = self._wrapped_list_clause(keyword, order)
        return self._argument_lines(f"{arg_sql}\n{clause}")

    # ------------------------------------------------------------------
    # Aggregate ORDER BY: `list(x ORDER BY k)`, `STRING_AGG(x, sep ORDER BY k)`,
    # `arg_max(x, y ORDER BY k)` all wrap the same way
    # ------------------------------------------------------------------

    def func(
        self,
        name: str,
        *args: t.Any,
        prefix: str = "(",
        suffix: str = ")",
        normalize: bool = True,
    ) -> str:
        values = [arg for arg in args if arg is not None and not isinstance(arg, bool)]
        order = values[-1] if values else None
        if self.pretty and (prefix, suffix) == ("(", ")") and self._is_aggregate_order(order):
            order = t.cast(exp.Order, order)
            func_name = self.normalize_func(name) if normalize else name
            return self._ordered_aggregate_sql(func_name, [*values[:-1], order.this], order)
        return super().func(name, *args, prefix=prefix, suffix=suffix, normalize=normalize)

    @staticmethod
    def _is_aggregate_order(arg: t.Any) -> bool:
        """True when *arg* is an aggregate's ``x ORDER BY …`` argument."""
        return isinstance(arg, exp.Order) and arg.args.get("this") is not None

    def _ordered_aggregate_sql(self, name: str, args: t.Sequence[exp.Expr | str], order: exp.Order) -> str:
        """Render the call ``name(args ORDER BY keys)`` of an aggregate with an ORDER BY.

        *args* are the call's arguments; the ORDER BY follows the last one.
        The call stays on one line while it fits. Otherwise its arguments go
        one per line, as in any wrapped call, and ORDER BY goes on its own
        line below them, its keys one per line if they don't fit on it
        either. A call that wraps only because it carries a comment keeps
        ORDER BY on its last argument's line (a ``--`` comment then ends
        the line instead of swallowing the ``)``).
        """
        arg_sqls = [self.sql(arg) for arg in args]
        clause = f"{self._order_keyword(order)} {self.expressions(order, flat=True)}"
        # The ORDER BY clause's own comments follow its keys, as sql(order) puts them.
        order_comments = self._inline_comments(order)
        inline = f"{name}({', '.join(arg_sqls)} {clause})"
        multiline = any("\n" in sql for sql in [*arg_sqls, clause])
        if not multiline and not self.too_wide([inline]):
            if not any(self._has_comments(arg) for arg in [*args, order] if isinstance(arg, exp.Expr)):
                return inline
            last = f"{arg_sqls[-1]} {clause}{order_comments}"
        else:
            last = self._order_below_sql(arg_sqls[-1], order) + order_comments
        return f"{name}({self._wrapped_args([*arg_sqls[:-1], last])})"

    @staticmethod
    def _is_order_by_all(expression: exp.Order) -> bool:
        if expression.args.get("this") is not None or expression.args.get("siblings"):
            return False
        if len(expression.expressions) != 1:
            return False

        ordered = expression.expressions[0]
        return (
            isinstance(ordered, exp.Ordered)
            and ordered.args.get("desc") is None
            and ordered.args.get("with_fill") is None
            and isinstance(ordered.this, exp.Var)
            and ordered.this.name.upper() == "ALL"
        )

    # ------------------------------------------------------------------
    # Window: OVER (...) stays inline, but a commented window spec breaks
    # into one clause per line so every -- comment ends its line.
    # ------------------------------------------------------------------

    def window_sql(self, expression: exp.Window) -> str:
        this = expression.this
        is_corr = isinstance(this, exp.Corr) or (isinstance(this, exp.Filter) and isinstance(this.this, exp.Corr))
        partition_by = expression.args.get("partition_by") or []
        order = expression.args.get("order")
        spec = expression.args.get("spec")
        commented = any(self._has_comments(part) for part in (*partition_by, order, spec) if part is not None)
        if not self.pretty or is_corr or not commented:
            return super().window_sql(expression)

        keyword = "AS" if expression.arg_key == "windows" else self.sql(expression, "over") or "OVER"
        # Body lines start one column in, like CASE: in a SELECT list that
        # lines the closing paren up under the function name.
        lines = [f"{self.sql(expression, 'this')} {keyword} ("]
        if expression.args.get("alias"):
            lines.append(f" {self.sql(expression, 'alias')}")
        if expression.args.get("first") is not None:
            lines.append(" FIRST" if expression.args["first"] else " LAST")
        if partition_by:
            lines.append(" PARTITION BY")
            lines.extend(f" {line}" for line in self.expressions(expression, key="partition_by").split("\n"))
        if order is not None:
            # A comment on ORDER BY itself stays on its own line above it.
            lines.extend(f" {line}" for line in self._render_comments(order.comments or [], leading=True).split("\n"))
            lines.append(" ORDER BY")
            lines.extend(f" {line}" for line in self.expressions(order).split("\n"))
        if spec is not None:
            lines.append(f" {self.sql(spec)}")
        lines.append(" )")
        return self.indent("\n".join(line for line in lines if line.strip()), skip_first=True, skip_last=True)

    def partition_by_sql(self, expression: exp.Window | exp.MatchRecognize) -> str:
        sql = super().partition_by_sql(expression)
        keys_hold_case = any(self._holds_case(key) for key in expression.args.get("partition_by") or [])
        if self.pretty and isinstance(expression, exp.Window) and (self.too_wide([sql]) or keys_hold_case):
            # A wrapped window puts each clause on its own line (format_args);
            # a PARTITION BY that still doesn't fit, such as one holding a
            # CASE, puts one key per line.
            return self._argument_lines(self._wrapped_list_clause("PARTITION BY", expression, key="partition_by"))
        return sql

    def _wrapped_list_clause(self, keyword: str, expression: exp.Expr, key: str | None = None) -> str:
        """Return *keyword* with its list one item per line below it, like a query's ORDER BY."""
        return f"{keyword}\n{self.expressions(expression, key=key)}"

    def _argument_lines(self, sql: str) -> str:
        """Shift the lines after the first one column right, for an argument of a wrapped call.

        In leading-comma style, _wrapped_args puts a one-character leader
        before an argument's first line only; the extra column keeps the
        argument's other lines in line with its first.
        """
        if not self.leading_comma:
            return sql
        return sql.replace("\n", "\n ")

    # ------------------------------------------------------------------
    # -> / ->>: render without surrounding spaces (value->>'key' not value ->> 'key').
    # sqlglot's default binary() always adds " op " padding; we bypass it here.
    # For static JSONPath expressions, also strip the $. prefix for simple
    # root+key paths ($.offer_key → 'offer_key'), matching DuckDB's short form.
    # Dynamic path expressions keep function-call syntax so formatter does not
    # change runtime semantics by forcing them through the JSON operators.
    # ------------------------------------------------------------------

    def jsonextract_sql(self, expression: exp.JSONExtract) -> str:
        if not self._is_static_json_path(expression.expression):
            return self.func("json_extract", expression.this, expression.expression)
        return f"{self.sql(expression, 'this')}->{self._json_path_sql(expression.expression)}"

    def jsonextractscalar_sql(self, expression: exp.JSONExtractScalar) -> str:
        if not self._is_static_json_path(expression.expression):
            return self.func("json_extract_string", expression.this, expression.expression)
        return f"{self.sql(expression, 'this')}->>{self._json_path_sql(expression.expression)}"

    def _is_static_json_path(self, path_expr: exp.Expr) -> bool:
        return isinstance(path_expr, exp.JSONPath)

    def _json_path_sql(self, path_expr: exp.Expr) -> str:
        """Render a static JSON path, using bare 'key' for simple root+key paths."""
        if (
            isinstance(path_expr, exp.JSONPath)
            and len(path_expr.expressions) == 2
            and isinstance(path_expr.expressions[0], exp.JSONPathRoot)
            and isinstance(path_expr.expressions[1], exp.JSONPathKey)
        ):
            return f"'{path_expr.expressions[1].this}'"
        return self.sql(path_expr)

    # ------------------------------------------------------------------
    # list_contains: preserve DuckDB's canonical name (sqlglot normalises
    # both list_contains and array_contains to ArrayContains and emits
    # array_contains; we override to always emit list_contains).
    # ------------------------------------------------------------------

    def arraycontains_sql(self, expression: exp.ArrayContains) -> str:
        return self.func("list_contains", expression.this, expression.expression)

    # ------------------------------------------------------------------
    # string_agg: prefer string_agg (PostgreSQL-compatible) over the
    # Oracle-style listagg alias that sqlglot's DuckDB generator emits.
    # The call wraps like any other: STRING_AGG(x, ', ' ORDER BY x) like
    # list(x ORDER BY x), STRING_AGG(x, ', ') like any call.
    # ------------------------------------------------------------------

    def groupconcat_sql(self, expression: exp.GroupConcat) -> str:
        this = expression.this
        if not self.pretty or isinstance(this, exp.Limit):
            return self._compact_groupconcat_sql(expression)
        # sqlglot writes the separator a call leaves out: string_agg's default, ','.
        separator = expression.args.get("separator") or exp.Literal.string(",")
        if self._is_aggregate_order(this):
            order = t.cast(exp.Order, this)
            return self._ordered_aggregate_sql(self.normalize_func("string_agg"), [order.this, separator], order)
        return self.func("string_agg", this, separator)

    def _compact_groupconcat_sql(self, expression: exp.GroupConcat) -> str:
        # _groupconcat_sql mutates the expression via order.this.pop(); copy to
        # avoid corruption when the generator visits the same node twice (e.g.
        # during AS-alignment width computation and then actual rendering).
        saved = self.pretty
        self.pretty = False
        try:
            sql = _groupconcat_sql(self, expression.copy(), func_name="string_agg", within_group=False)
        finally:
            self.pretty = saved
        if self.pretty and self._has_inner_comments(expression) and sql.endswith(")"):
            # The compact form would let a -- comment swallow the closing
            # paren, so put the arguments on their own line.
            name, _, inner = sql[:-1].partition("(")
            return f"{name}({self._wrapped_args([inner])})"
        return sql

    # ------------------------------------------------------------------
    # coalesce: keep canonical lowercase function name.
    # Two-argument COALESCE → ifnull rewrite is handled by
    # PreferIfnullOverCoalesceRule before generation.
    # ------------------------------------------------------------------

    def coalesce_sql(self, expression: exp.Coalesce) -> str:
        return self.func("coalesce", expression.this, *expression.expressions)

    # ------------------------------------------------------------------
    # Cast: prefer :: shorthand over CAST()
    # ------------------------------------------------------------------

    def cast_sql(self, expression: exp.Cast, safe_prefix: str | None = None) -> str:
        if safe_prefix:
            # TRY_CAST — keep verbose form
            return super().cast_sql(expression, safe_prefix=safe_prefix)
        type_sql = self.sql(expression, "to")
        # Struct literal (val1, val2, ...)::type — apply leading-comma style when the
        # tuple wraps across lines (our expressions() always wraps 2+ items).
        if self.pretty and self.leading_comma and isinstance(expression.this, exp.Tuple):
            exprs_sql = self.expressions(expression.this, flat=False)
            return f"(\n{exprs_sql}\n)::{type_sql}"

        value_sql = self.sql(expression, "this")
        if self._needs_cast_parens(expression.this):
            value_sql = f"({value_sql})"

        return f"{value_sql}::{type_sql}"

    def _needs_cast_parens(self, value: exp.Expr) -> bool:
        """Return True when ``value::type`` would cast only part of *value*.

        ``::`` binds tighter than every operator except ``.``, so an operator
        expression keeps its grouping in parentheses: ``CAST(a + b AS int)`` is
        ``(a + b)::int``, not ``a + b::int``. That includes JSON extraction:
        ``(j->'x')::int``.
        """
        if isinstance(value, (exp.Paren, exp.Dot)):
            return False
        return isinstance(value, (exp.Binary, exp.Unary, exp.Predicate, exp.Interval))

    # ------------------------------------------------------------------
    # Lambda: DuckDB's `lambda x: body` syntax; wrap body when the flat form
    # exceeds max_line_length
    # ------------------------------------------------------------------

    # DuckDB functions that take a lambda argument. sqlglot parses `a -> b`
    # inside any call as a lambda, but outside these functions DuckDB reads it
    # as the JSON operator (`ifnull(doc -> 'key', …)`), so only arrows passed to
    # these functions are rewritten to `lambda` syntax.
    _LAMBDA_FUNCS = frozenset(
        {
            "list_transform",
            "array_transform",
            "list_apply",
            "array_apply",
            "apply",
            "list_filter",
            "array_filter",
            "filter",
            "list_reduce",
            "array_reduce",
            "reduce",
        }
    )

    def lambda_sql(self, expression: exp.Lambda, arrow_sep: str = "->", wrap: bool = True) -> str:
        # DuckDB deprecated the arrow form (`x -> body`) in favour of
        # `lambda x: body`. Its parameters take no parentheses:
        # `lambda acc, x: acc + x`.
        params = self.expressions(expression, flat=True)
        if expression.args.get("colon") or self._is_lambda_function_arg(expression):
            head = f"lambda {params}:"
        else:
            if wrap and len(params.split(",")) > 1:
                params = f"({params})"
            head = f"{params} {arrow_sep}"
        body_sql = self.sql(expression, "this")
        flat = f"{head} {body_sql}"
        if not self.pretty:
            return flat
        # Only wrap when the entire lambda string is a single line that exceeds
        # max_line_length.  If the body is already multi-line (e.g. a struct cast
        # that wrapped independently), leave the result as-is — the caller context
        # (format_args) will handle indentation.
        if "\n" in flat or not self.too_wide([flat]):
            return flat
        # Flat single-line lambda is too wide — move the body to its own line,
        # indented one level below the parameters.
        return f"{head}\n{self.indent(body_sql)}"

    def _is_lambda_function_arg(self, expression: exp.Lambda) -> bool:
        # The lambda follows the list. An arrow anywhere else is JSON, e.g. the
        # list in `list_transform(doc -> 'items', lambda x: …)`.
        parent = expression.parent
        if isinstance(parent, (exp.Transform, exp.ArrayFilter)):
            return expression.arg_key == "expression"
        if isinstance(parent, exp.Columns):
            # COLUMNS(lambda c: …) selects the columns whose name matches.
            return expression.arg_key == "this"
        if isinstance(parent, exp.Anonymous) and parent.name.lower() in self._LAMBDA_FUNCS:
            # In method-call syntax, `list.list_filter(lambda x: …)`, the list is
            # the receiver, so the lambda is the first argument.
            is_method_call = isinstance(parent.parent, exp.Dot) and parent.arg_key == "expression"
            return expression.index == (0 if is_method_call else 1)
        return False

    # ------------------------------------------------------------------
    # ArrayAgg → list(): DuckDB canonical aggregate name
    # array_agg() is an alias; jarify always emits list() regardless of input.
    # Also handles DISTINCT with wrapping when pretty-printing.
    # list_sql handles the same wrapping for List nodes (idempotency: list(DISTINCT ...)
    # re-parses as exp.List, not exp.ArrayAgg).
    # ------------------------------------------------------------------

    def arrayagg_sql(self, expression: exp.ArrayAgg) -> str:
        func_name = self.normalize_func("list")
        distinct = expression.this if isinstance(expression.this, exp.Distinct) else None
        if self.pretty and distinct is not None:
            exprs_sqls = [self.sql(e) for e in distinct.expressions]
            # Wrap when any expression is already multi-line, or when the flat inline is too wide
            any_multiline = any("\n" in s for s in exprs_sqls)
            flat_inline = f"{func_name}(DISTINCT {', '.join(exprs_sqls)})"
            if any_multiline or self.too_wide([flat_inline]):
                exprs_str = "\n".join(exprs_sqls)
                inner = self.indent(f"\nDISTINCT {exprs_str}\n", skip_first=True, skip_last=True)
                result = f"{func_name}({inner})"
                return self._add_arrayagg_null_filter(result, expression, expression.this)
        # Non-DISTINCT, compact mode, or DISTINCT that fits inline: emit list(<inner>).
        # format_args wraps a too-wide or commented argument the way list_sql's
        # fallback does; sqlglot parses list(x ORDER BY y) as ArrayAgg, so this
        # path must match it. An ORDER BY wraps as in any aggregate (func()).
        if self.pretty and self._is_aggregate_order(expression.this):
            order = t.cast(exp.Order, expression.this)
            result = self._ordered_aggregate_sql(func_name, [order.this], order)
        else:
            result = f"{func_name}({self.format_args(expression.this)})"
        return self._add_arrayagg_null_filter(result, expression, expression.this)

    def list_sql(self, expression: exp.List) -> str:
        """Handle exp.List with DISTINCT wrapping (mirrors arrayagg_sql for idempotency).

        list(DISTINCT ...) re-parses as exp.List (not exp.ArrayAgg), so this
        method must apply the same DISTINCT-wrapping logic to keep formatting
        stable across multiple passes.
        """
        func_name = self.normalize_func("list")
        # expressions[0] is Distinct when written as list(DISTINCT ...)
        distinct = expression.expressions[0] if expression.expressions else None
        if not (self.pretty and isinstance(distinct, exp.Distinct)):
            # Non-DISTINCT or compact mode: delegate to default
            return super().function_fallback_sql(expression)
        exprs_sqls = [self.sql(e) for e in distinct.expressions]
        any_multiline = any("\n" in s for s in exprs_sqls)
        flat_inline = f"{func_name}(DISTINCT {', '.join(exprs_sqls)})"
        if not any_multiline and not self.too_wide([flat_inline]):
            return super().function_fallback_sql(expression)
        exprs_str = "\n".join(exprs_sqls)
        inner = self.indent(f"\nDISTINCT {exprs_str}\n", skip_first=True, skip_last=True)
        return f"{func_name}({inner})"

    def format_args(self, *args: t.Any, sep: str = ", ") -> str:
        args = tuple(arg for arg in args if arg is not None and not isinstance(arg, bool))
        arg_sqls = tuple(self.sql(arg) for arg in args)
        if self.pretty and (
            self.too_wide(arg_sqls)
            or self._has_commented_arg(args, sep)
            or self._has_multiline_case_arg(args, arg_sqls, sep)
            or self._has_multiline_clause(arg_sqls, sep)
        ):
            return self._wrapped_args(arg_sqls, sep=sep)
        return sep.join(arg_sqls)

    @staticmethod
    def _has_multiline_clause(arg_sqls: t.Sequence[str], sep: str) -> bool:
        """A window spec's clauses (space-separated) go one per line when one of
        them spans lines, such as a PARTITION BY or ORDER BY holding a CASE."""
        return sep == " " and any("\n" in sql for sql in arg_sqls)

    def _has_commented_arg(self, args: t.Sequence[t.Any], sep: str) -> bool:
        """A commented argument wraps the call one argument per line, so its
        -- comment ends the line instead of swallowing the rest of the call."""
        return sep.strip() == "," and any(isinstance(a, exp.Expr) and self._has_comments(a) for a in args)

    def _has_multiline_case_arg(self, args: t.Sequence[t.Any], arg_sqls: t.Sequence[str], sep: str) -> bool:
        """An argument holding a multi-line CASE wraps the call one argument
        per line, so the CASE is laid out as in a SELECT list instead of
        starting partway along the call's line."""
        return sep.strip() == "," and any(
            "\n" in sql and isinstance(arg, exp.Expr) and self._holds_case(arg)
            for arg, sql in zip(args, arg_sqls, strict=True)
        )

    def _wrapped_args(self, arg_sqls: t.Sequence[str], sep: str = ", ") -> str:
        """Lay out call arguments one per line, between the call's parentheses."""
        if self.leading_comma:
            # Only a comma-separated list gets leading commas. Space-separated
            # parts, such as a window's PARTITION BY / ORDER BY / frame
            # clauses, go one per line aligned with the first.
            leader = "," if sep.strip() == "," else " "
            parts = [f" {arg_sqls[0]}"]
            parts.extend(f"{leader}{sql}" for sql in arg_sqls[1:])
            return self.indent("\n" + "\n".join(parts) + "\n", skip_first=True, skip_last=True)
        return self.indent("\n" + f"{sep.strip()}\n".join(arg_sqls) + "\n", skip_first=True, skip_last=True)

    # ------------------------------------------------------------------
    # Data types — always lowercase (text, int, timestamp, …)
    # ------------------------------------------------------------------

    def datatype_sql(self, expression: exp.DataType) -> str:
        # For STRUCT types in pretty+leading-comma mode, build the field list directly
        # with jarify's ",field" style instead of delegating to super().datatype_sql()
        # which calls expressions() with new_line/dynamic/skip_first/skip_last — a
        # combination that interacts with the DataType bypass in expressions() and
        # produces the base generator's ", field" (comma-space) style instead of
        # jarify's ",field" (comma-only) style.
        if self.pretty and self.leading_comma and expression.this == exp.DType.STRUCT:
            fields = expression.expressions
            if not fields:
                return "struct()"
            field_sqls = [self.sql(f) for f in fields]
            # Stay inline when all fields comfortably fit on one line
            if not self.too_wide(field_sqls):
                return f"struct({', '.join(field_sqls)})"
            # Multi-line: leading-comma jarify style
            # First field gets " " leader, rest get "," leader; indent the whole block.
            parts = [f" {field_sqls[0]}"]
            parts.extend(f",{s}" for s in field_sqls[1:])
            inner = self.indent("\n".join(parts))
            # The closing ")" carries a 1-space prefix so it aligns with the opening
            # expression in leading-comma contexts (compensates for the 1-char leader).
            return f"struct(\n{inner}\n )"
        sql = super().datatype_sql(expression).lower()
        # Apply the same closing-paren alignment fix to any other multi-line STRUCT
        # type that was formatted by the base generator (e.g. trailing-comma mode).
        if self.pretty and expression.this == exp.DType.STRUCT and "\n" in sql:
            last_newline_close = sql.rfind("\n)")
            if last_newline_close != -1:
                sql = sql[:last_newline_close] + "\n )" + sql[last_newline_close + 2 :]
        return sql

    def boolean_sql(self, expression: exp.Boolean) -> str:
        return "true" if expression.this else "false"

    # ------------------------------------------------------------------
    # CREATE MACRO: opening paren on its own line, leading-comma params
    # ------------------------------------------------------------------

    def userdefinedfunction_sql(self, expression: exp.UserDefinedFunction) -> str:
        this = self.sql(expression, "this")
        if not expression.args.get("wrapped") or not self.pretty:
            return super().userdefinedfunction_sql(expression)

        # Pretty + wrapped: build param list without indentation to avoid the
        # double-indent that occurs when self.wrap() re-indents an already-indented
        # string produced by self.expressions().  Apply a single indent pass here.
        params = self.no_identify(self.expressions, expression, indent=False)
        if not params.strip():
            return this
        indented = self.indent(params)
        return f"{this}\n(\n{indented}\n)"

    # ------------------------------------------------------------------
    # CREATE TABLE: opening paren on its own line, column alignment,
    # blank line before table-level constraints
    # ------------------------------------------------------------------

    def schema_sql(self, expression: exp.Schema) -> str:
        this = self.sql(expression, "this")
        sql = self.schema_columns_sql(expression)
        if this and sql and self.pretty:
            return f"{this}\n{sql}"
        return f"{this} {sql}" if this and sql else this or sql

    def schema_columns_sql(self, expression: exp.Expr) -> str:  # type: ignore[override]
        if not expression.expressions:
            return ""
        if not self.pretty:
            return super().schema_columns_sql(expression)

        col_defs = [e for e in expression.expressions if isinstance(e, exp.ColumnDef)]
        table_constraints = [e for e in expression.expressions if not isinstance(e, exp.ColumnDef)]

        # Compute alignment widths across all column definitions
        col_name_width = max((len(self.sql(c, "this")) for c in col_defs), default=0)
        type_width = max(
            (len(self.sql(c, "kind")) for c in col_defs if self.sql(c, "kind")),
            default=0,
        )

        saved_name = self._col_name_align
        saved_type = self._col_type_align
        self._col_name_align = col_name_width
        self._col_type_align = type_width
        try:
            col_sqls = [self.columndef_sql(c) for c in col_defs]
            constraint_sqls = [self.sql(c) for c in table_constraints]
        finally:
            self._col_name_align = saved_name
            self._col_type_align = saved_type

        # Build body with leading-comma style
        lines: list[str] = []
        for i, sql in enumerate(col_sqls):
            leader = " " if i == 0 else ","
            lines.append(f"{leader}{sql}")

        if constraint_sqls:
            lines.append("")  # blank line separating columns from table constraints
            for sql in constraint_sqls:
                lines.append(f",{sql}")

        # Indent each non-blank line by pad spaces; keep blank lines clean
        indented = [(" " * self.pad + line) if line else "" for line in lines]
        body = "\n".join(indented)
        return f"(\n{body}\n)"

    def columndef_sql(self, expression: exp.ColumnDef, sep: str = " ") -> str:
        column = self.sql(expression, "this")
        kind = self.sql(expression, "kind")
        constraints_sql = self.expressions(expression, key="constraints", sep=" ", flat=True)
        exists = "IF NOT EXISTS " if expression.args.get("exists") else ""
        position = self.sql(expression, "position")

        if expression.find(exp.ComputedColumnConstraint) and not self.COMPUTED_COLUMN_WITH_TYPE:
            kind = ""

        # Apply column name padding when inside a CREATE TABLE schema body
        col_part = column.ljust(self._col_name_align) if self._col_name_align else column

        # Pad type to align constraints column, but only when this column has constraints
        if self._col_type_align and kind and constraints_sql:
            kind_part = f"{sep}{kind.ljust(self._col_type_align)}"
        else:
            kind_part = f"{sep}{kind}" if kind else ""

        constraints_part = f" {constraints_sql}" if constraints_sql else ""
        position_part = f" {position}" if position else ""
        return f"{exists}{col_part}{kind_part}{constraints_part}{position_part}"
