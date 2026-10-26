"""Custom DuckDB SQL generator with full control over formatting style.

Subclasses sqlglot's DuckDBGenerator to enforce jarify's opinionated rules:
- Configurable indentation width
- Leading-comma style: ,col aligned with content at pad+1
- Bare JOIN → INNER JOIN normalization
- AND/OR conditions always on separate lines in pretty mode
- WHERE/HAVING/ON: first condition inline with keyword, AND/OR right-justified
  so all condition content aligns at the same column; = operators in WHERE
  top-level AND conditions are column-aligned (padded to max LHS width + 1)
- CTE: opening paren on its own line, comma-prefix separator
- Consistent keyword casing; DuckDB functions in lowercase
- IS NOT NULL preserved (not rewritten to NOT x IS NULL)
- NULLS LAST/FIRST suppressed when it matches DuckDB's default
- SELECT * FROM t → FROM t (DuckDB FROM-first syntax)
- JSON extraction casts keep grouping: (json_expr->'path')::type
- Dynamic JSON extraction paths stay as function calls; only static paths use -> / ->>
- Struct tuple casts (val, ...)::type use leading-comma style when multi-line
- DISTINCT inside aggregates appears on its own line when the call wraps
- CREATE TABLE: opening paren on its own line, column name/type alignment,
  blank line before table-level constraints
- Aggregate and window functions (COUNT, SUM, ROW_NUMBER, RANK, …) are uppercase;
  all other DuckDB built-in functions remain lowercase
- FROM/JOIN block: AS omitted from table aliases; ON/USING inline; aliases
  column-aligned when the block contains only simple (single-line) table refs
- A -- comment never swallows SQL: commented windows, calls and IN lists take
  their multi-line form; any other comment followed by SQL becomes /* */
"""

from __future__ import annotations

import functools
import re
import typing as t
from typing import TYPE_CHECKING, ClassVar

import sqlglot.expressions as exp
from sqlglot.dialects.dialect import groupconcat_sql as _groupconcat_sql
from sqlglot.dialects.duckdb import DuckDB

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
        self._as_align_width: int | None = None  # set during SELECT expression rendering
        self._tree_as_align_column: int | None = None  # visible AS column target per statement tree during generate()
        self._col_name_align: int | None = None  # set during CREATE TABLE column rendering
        self._col_type_align: int | None = None  # set during CREATE TABLE column rendering
        self._join_alias_col: int | None = None  # set during FROM/JOIN block rendering
        self._leading_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._trailing_sep_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._connector_force_expand: bool = False  # set True inside WHERE/HAVING to always break AND/OR
        self._block_comment_texts: frozenset[str] = frozenset()  # comments generate() renders as /* */

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
            for c in node.comments or []
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
        saved_align = self._tree_as_align_column
        if self.pretty:
            self._tree_as_align_column = self._compute_tree_as_align_column(expression)
        try:
            return restore_comment_lines(super().generate(expression, copy=copy))
        finally:
            self._tree_as_align_column = saved_align

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
    # Function name casing: aggregates/window functions → UPPER, rest → lower
    # ------------------------------------------------------------------

    def normalize_func(self, name: str) -> str:
        return name.upper() if name.lower() in self._UPPERCASE_FUNCS else name.lower()

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
                else self._compute_as_align_width(list(expressions_list))
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
                    lead = [c for c in e.comments if c.strip() in self._leading_comment_texts]
                    trail_sep = [c for c in e.comments if c.strip() in self._trailing_sep_comment_texts]
                    trail = [
                        c
                        for c in e.comments
                        if c.strip() not in self._leading_comment_texts
                        and c.strip() not in self._trailing_sep_comment_texts
                    ]
                    for c in lead:
                        result_sqls.append(f" {prefix}-- {c.strip()}")
                    inline = self._render_comments(trail)
                    result_sqls.append(f"{leader}{prefix}{sql}{inline}")
                    for c in trail_sep:
                        result_sqls.append(f"{prefix}-- {c.strip()}")
                else:
                    inline = self._inline_comments(e) if isinstance(e, exp.Expr) else ""
                    result_sqls.append(f"{leader}{prefix}{sql}{inline}")
        finally:
            self._as_align_width = saved_align

        result_sql = "\n".join(s.rstrip() for s in result_sqls)
        # dynamic=True means "wrap only if necessary" — stay inline when content fits.
        # Commented items never go inline: a -- comment would swallow the rest of the line.
        commented = dynamic and any(isinstance(e, exp.Expr) and self._has_comments(e) for e in expressions_list)
        if dynamic and not commented and not self.too_wide(result_sqls):
            return sep.join(s.lstrip(",").lstrip() for s in result_sqls)
        if dynamic and commented and new_line:
            # Put the items between their own ( and ) lines, like wrapped call
            # arguments, so the last item's comment can't swallow the ")".
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
        if min_column_alias is None:
            return align_column
        return max(align_column, min_column_alias)

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

        In pretty mode, each expression line gets the generator pad plus the
        leading-comma marker (` ` for the first row, `,` for subsequent rows).
        Every ancestor SELECT adds one more indent level around the nested
        statement, so nested CTEs/subqueries shift the visible `AS` column.
        """
        ancestor_selects = 0
        parent = select.parent
        while parent is not None:
            if isinstance(parent, exp.Select):
                ancestor_selects += 1
            parent = parent.parent
        return self.pad + 1 + (ancestor_selects * self._indent)

    def _collect_as_alignment_metrics(self, expressions_list: list) -> tuple[list[int], int]:
        """Return ``(column_widths, alias_count)`` for a SELECT expression list.

        For single-line aliased expressions the width is simply ``len(col_sql)``.
        For multi-line aliased expressions (e.g. scalar subqueries, CASE blocks)
        the effective width is ``max(0, len(last_line.lstrip()) - 1)``.

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
                if "\n" in col_sql:
                    last_line = col_sql.splitlines()[-1]
                    # Subtract 1: cancels the +1 compensation in alias_sql so that
                    # SELECT lists with only multi-line expressions don't produce a
                    # spurious extra space before AS.
                    col_widths.append(max(0, len(last_line.lstrip()) - 1))
                else:
                    col_widths.append(len(col_sql))
            else:
                # Non-aliased single-line columns count toward the alignment
                # width so AS keywords clear the longest expression in the list.
                # Measure without comments, as expressions() renders the column:
                # a comment after it or on its own line shouldn't move the AS.
                col_sql = self.sql(e, comment=False)
                if "\n" not in col_sql:
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
        if align_width is not None and isinstance(expression.parent, (exp.Select, exp.Star)):
            if "\n" in this_sql:
                lines = this_sql.splitlines()
                # For multi-line expressions the last line (e.g. ``)``, ``END``)
                # has no leader character prepended in the expressions loop
                # (the `` ``/``,`` leader only goes on the first line).  To land
                # ``AS`` at the same visual column as single-line aliases — which
                # DO carry a 1-char leader — we add an extra +1 to the padding.
                padding = " " * max(0, align_width - len(lines[-1]) + 1)
                lines[-1] = f"{lines[-1]}{padding} AS {alias_name}"
                return "\n".join(lines)
            padding = " " * max(0, align_width - len(this_sql))
            return f"{this_sql}{padding} AS {alias_name}"
        return f"{this_sql} AS {alias_name}"

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
        # Pop comments to prevent double-rendering.  sqlglot attaches leading
        # comments to the TableAlias child, not the CTE node itself, so we
        # must pop from both.  Leading comments (own-line before the CTE name)
        # are prepended as separate lines; trailing comments stay inline after AS.
        comments = expression.pop_comments() or []
        alias_node = expression.args.get("alias")
        if alias_node:
            comments = comments + (alias_node.pop_comments() or [])
        alias_sql = self.sql(expression, "alias")

        if self._leading_comment_texts:
            lead = [c for c in comments if c.strip() in self._leading_comment_texts]
            trail = [c for c in comments if c.strip() not in self._leading_comment_texts]
        else:
            lead, trail = [], comments

        trail = [c for c in trail if c.strip()]
        if len(trail) > 1:
            # Only one `--` comment fits after AS, since it ends the line, and
            # sqlglot drops comments placed between AS and the opening paren.
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

        body = f"{alias_sql} AS{materialized_str}{comment_suffix}\n{self.wrap(expression)}"

        return self._render_comments(lead, leading=True), body

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
    # ------------------------------------------------------------------

    def _normalize_bare_join(self, expression: exp.Join) -> exp.Join:
        """Write a bare JOIN that has an ON or USING condition as INNER JOIN."""
        has_condition = expression.args.get("on") or expression.args.get("using")
        if expression.side or expression.kind or expression.method or not has_condition:
            return expression
        normalized = expression.copy()
        normalized.set("kind", "INNER")
        return normalized

    def join_sql(self, expression: exp.Join) -> str:
        has_condition = expression.args.get("on") or expression.args.get("using")
        if not expression.side and not expression.kind and not expression.method:
            if has_condition:
                # Bare JOIN with a condition — normalize to INNER JOIN
                expression = self._normalize_bare_join(expression)
            else:
                # Comma join (no condition) — delegate to DuckDB's renderer,
                # which emits comma-separated syntax instead of a bare JOIN keyword
                return super().join_sql(expression)
        elif expression.side in ("LEFT", "RIGHT") and expression.kind == "OUTER":
            # DROP redundant OUTER: LEFT OUTER JOIN → LEFT JOIN
            expression = expression.copy()
            expression.set("kind", None)

        if not self.pretty:
            return super().join_sql(expression)

        op_sql = self._join_keyword(expression)
        this = expression.this

        if self._join_alias_col is not None and isinstance(this, exp.Table):
            table_ref = self.table_parts(this)
            alias_str = self._table_alias_str(this)
            if alias_str:
                pad = " " * max(
                    1, self._join_alias_col - len(op_sql) - 1 - len(table_ref) - self._table_alias_width(this)
                )
                return self.seg(self._inline_on_sql(expression, f"{op_sql} {table_ref}{pad}{alias_str}"))
            return self.seg(self._inline_on_sql(expression, f"{op_sql} {table_ref}"))

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
            alias_str = self._table_alias_str(this)
            this_sql = f"{table_ref} {alias_str}" if alias_str else table_ref
        else:
            this_sql = self.sql(this)

        exprs = self.expressions(expression)
        if exprs:
            this_sql = f"{this_sql},{self.seg(exprs)}"

        return self.seg(self._inline_on_sql(expression, f"{op_sql} {this_sql}"))

    def from_sql(self, expression: exp.From) -> str:
        table = expression.this
        if not self.pretty:
            return super().from_sql(expression)

        if isinstance(table, exp.Subquery):
            # Render compactly; non-pretty seg() prepends a space, so strip it.
            # A commented subquery can't go on one line (a -- comment would
            # swallow the rest of it).
            compact = self._compact_sql(expression).strip()
            if not self._has_comments(table) and not self.too_wide([compact]):
                return self.seg(compact)
            return super().from_sql(expression)

        if not isinstance(table, exp.Table):
            return super().from_sql(expression)

        alias_str = self._table_alias_str(table)
        if not alias_str:
            return super().from_sql(expression)

        table_ref = self.table_parts(table)
        if self._join_alias_col is not None:
            pad = " " * max(1, self._join_alias_col - len("FROM") - 1 - len(table_ref) - self._table_alias_width(table))
            return self.seg(f"FROM {table_ref}{pad}{alias_str}")
        return self.seg(f"FROM {table_ref} {alias_str}")

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

    def _table_alias_str(self, table: exp.Table) -> str:
        """Return the alias string for a table node, or empty string if none."""
        alias_node = table.args.get("alias")
        return self.sql(alias_node) if alias_node else ""

    def _table_alias_width(self, table: exp.Table) -> int:
        """Return the alias's width for alignment: without its comments, which
        follow the alias on the line."""
        alias_node = table.args.get("alias")
        return len(self.sql(alias_node, comment=False)) if alias_node else 0

    def _inline_on_sql(self, expression: exp.Join, head: str) -> str:
        """Append the ON or USING clause to the JOIN line *head*.

        The ON condition stays inline on one line. A commented condition
        cannot (a ``--`` comment would swallow the rest of the line), so it is
        laid out like WHERE: AND/OR on their own lines, right-justified so the
        conditions align after ``ON``.
        """
        on_expr = expression.args.get("on")
        using = expression.args.get("using")
        if on_expr:
            if self._has_comments(on_expr):
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
        joins = expression.args.get("joins") or []
        if not from_expr:
            return None

        entries: list[tuple[int, str, exp.Expr]] = []

        from_ref = self._table_ref_only_sql(from_expr.this)
        if from_ref is None:
            return None
        entries.append((len("FROM"), from_ref, from_expr.this))

        for join in joins:
            # Normalize the keyword before measuring its length so the alignment
            # width matches what join_sql actually renders.  For example,
            # LEFT OUTER JOIN (15 chars) is rendered as LEFT JOIN (9 chars), and
            # a bare JOIN (4 chars) as INNER JOIN (10 chars), so we must use the
            # post-normalization keyword here.
            if join.side in ("LEFT", "RIGHT") and join.kind == "OUTER":
                normalized = join.copy()
                normalized.set("kind", None)
                kw = self._join_keyword(normalized)
            else:
                kw = self._join_keyword(self._normalize_bare_join(join))
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
                op_comments.append(node.comments or [])
            self._flatten_connector(node.right, terms, ops, op_comments)
        else:
            terms.append(self.sql(node))

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

        compact = self._compact_sql(expression.this)
        if not self._has_comments(expression.this) and not self.too_wide([f"({compact})"]):
            sql = f"({compact})"
        else:
            sql = super().paren_sql(expression)

        inline = self._render_comments(trail) if trail else ""
        if lead:
            rendered_lead = "\n".join(f"-- {c.strip()}" for c in lead if c.strip())
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
        wide.
        """
        has_else = expression.args.get("false") is not None

        if not self.pretty:
            if has_else:
                return self.func("IF", expression.this, expression.args["true"], expression.args["false"])
            return self.func("IF", expression.this, expression.args["true"])

        # Pretty mode: keep the condition compact so AND/OR chains do not
        # wrap mid-call. Branches start compact too, but can fall back to
        # their normal SQL rendering when still too wide on their own.
        compact_cond = self._compact_sql(expression.this)
        true_expr = expression.args["true"]
        compact_then = self._compact_sql(true_expr)
        compact_args = [compact_cond, compact_then]

        false_expr = expression.args.get("false")
        if false_expr is not None:
            compact_args.append(self._compact_sql(false_expr))

        # A commented argument can't be rendered compactly (a -- comment would
        # swallow the rest of the line), so it forces the expanded form and
        # keeps its normal multi-line rendering.
        def _fits(arg: exp.Expr, compact: str) -> bool:
            return not self._has_comments(arg) and not self.too_wide([compact])

        inline = f"if({', '.join(compact_args)})"
        args = [a for a in (expression.this, true_expr, false_expr) if a is not None]
        if not any(self._has_comments(a) for a in args) and not self.too_wide([inline]):
            return inline

        branch_sqls = [self.sql(expression.this) if self._has_comments(expression.this) else compact_cond]
        branch_sqls.append(compact_then if _fits(true_expr, compact_then) else self.sql(true_expr))
        if false_expr is not None:
            compact_false = self._compact_sql(false_expr)
            branch_sqls.append(compact_false if _fits(false_expr, compact_false) else self.sql(false_expr))

        # Too wide: expand the outer IF() with leading commas. Keep the
        # condition on one compact line, but allow branch expressions to bring
        # along their own nested wrapping.
        p = self.pad

        def _prefixed(arg_sql: str, *, first: str, rest: str) -> list[str]:
            lines = arg_sql.splitlines() or [arg_sql]
            return [f"{first}{lines[0]}", *(f"{rest}{line}" for line in lines[1:])]

        lines = ["if("]
        lines.extend(_prefixed(branch_sqls[0], first=" " * (p + 2), rest=" " * (p + 2)))
        for arg_sql in branch_sqls[1:]:
            lines.extend(_prefixed(arg_sql, first=" " * (p + 1) + ",", rest=" " * (p + 2)))
        lines.append(")")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # CASE: simple CASE keeps WHEN/THEN on one line; searched CASE puts
    # THEN on its own line and expands AND/OR conditions inside WHEN.
    # ------------------------------------------------------------------

    def case_sql(self, expression: exp.Case) -> str:
        this = self.sql(expression, "this")

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
            else:
                wp = self._compact_sql(wp_expr) if wp_expr is not None else self.sql(e, "this")

            true_expr = e.args.get("true")
            if self.pretty and true_expr is not None:
                compact = self._compact_sql(true_expr)
                tp = compact if not self.too_wide([f"THEN {compact}"]) else self.sql(e, "true")
            else:
                tp = self.sql(e, "true")
            when_parts.append(wp)
            then_parts.append(tp)

        default_expr = expression.args.get("default")
        default_sql: str | None = None
        if default_expr is not None:
            if self.pretty:
                compact = self._compact_sql(default_expr)
                default_sql = compact if not self.too_wide([f"ELSE {compact}"]) else self.sql(expression, "default")
            else:
                default_sql = self.sql(expression, "default")

        def _append_multiline(
            stmts: list[str], keyword: str, value: str, *, prefix: str = "", continuation_prefix: str = ""
        ) -> None:
            lines = value.splitlines()
            stmts.append(f"{prefix}{keyword} {lines[0]}")
            stmts.extend(f"{continuation_prefix}{line}" for line in lines[1:])

        def _build_simple(align: bool) -> list[str]:
            max_w = max((len(w) for w in when_parts), default=0) if align else 0
            stmts = [f"CASE {this}" if this else "CASE"]
            for wp, tp in zip(when_parts, then_parts, strict=True):
                stmts.append(f"WHEN {wp.ljust(max_w)} THEN {tp}")
            if default_sql is not None:
                stmts.append(f"ELSE {default_sql}")
            stmts.append("END")
            return stmts

        def _searched_when_prefix(line: str) -> str:
            return "   " if line.startswith("OR ") else "  "

        def _build_searched() -> list[str]:
            stmts = ["CASE"]
            for wp, tp in zip(when_parts, then_parts, strict=True):
                wp_lines = wp.splitlines()
                stmts.append(f" WHEN {wp_lines[0]}")
                continuation = wp_lines[1:]
                prefixes = [_searched_when_prefix(line) for line in continuation]
                stmts.extend(self._prefix_lines(continuation, prefixes))
                _append_multiline(stmts, "THEN", tp, prefix=" ", continuation_prefix="  ")
            if default_sql is not None:
                _append_multiline(stmts, "ELSE", default_sql, prefix=" ", continuation_prefix="  ")
            stmts.append(" END")
            return stmts

        if not self.pretty:
            return " ".join(_build_simple(align=False))

        if not this:
            return self.indent("\n".join(_build_searched()), skip_first=True, skip_last=True)

        align = len(when_parts) >= 2 and all("\n" not in tp for tp in then_parts)
        return self.indent("\n".join(_build_simple(align=align)), skip_first=True, skip_last=True)

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
        if not self.pretty or not isinstance(expression.this, exp.And):
            return self._inline_clause_sql("WHERE", expression)

        operands = self._flatten_and(expression.this)
        conditions = [cond for cond, _ in operands]

        # Max EQ LHS width across top-level AND operands only — nested EQs (inside
        # Paren, subqueries, etc.) must not influence padding of sibling conditions.
        eq_lhs_widths = [len(self.sql(cond.this)) for cond in conditions if isinstance(cond, exp.EQ)]
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
                    if isinstance(cond, exp.Paren) and self._has_comments(cond)
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
            return left + self._flatten_and(condition.expression, condition.comments or [])
        return [(condition, comments or [])]

    def _has_comments(self, expression: exp.Expr | None) -> bool:
        """Return True when expression or any descendant carries SQL comments."""
        if expression is None:
            return False
        return any(getattr(node, "comments", None) for node in expression.walk())

    def _has_inner_comments(self, expression: exp.Expr) -> bool:
        """Return True when a descendant of expression (not expression itself) carries comments."""
        return any(node.comments for node in expression.walk() if node is not expression)

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
        return self._inline_clause_sql("HAVING", expression)

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
        if isinstance(this, exp.Connector) and not self._has_comments(this):
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
        An own-line comment lines up with the AND/OR it precedes.
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

        for line in lines[1:]:
            if depth == 0 and line.startswith(("AND ", "OR ")):
                connector_width = len(line.split(" ", 1)[0]) + 1
                prefixes.append(" " * max(0, keyword_width - connector_width))
            else:
                # Pass continuation lines through as-is; child methods (e.g.
                # in_sql) are responsible for their own relative indentation.
                prefixes.append("")
            if not self._is_comment_line(line):
                code = self._code_part(line)
                depth += code.count("(") - code.count(")")

        return [f"{keyword} {lines[0]}", *self._prefix_lines(lines[1:], prefixes)]

    # ------------------------------------------------------------------
    # IS NOT NULL: preserve original form instead of NOT x IS NULL
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # IN (subquery): opening paren on its own line
    # ------------------------------------------------------------------

    def in_sql(self, expression: exp.In) -> str:
        """Render IN with a subquery inline when it fits, multiline otherwise.

        When the compact form ``col IN (SELECT ...)`` fits within
        ``max_line_length``, it is kept on a single line.  Only when the
        inline form would exceed the threshold does it fall back to the
        block style::

            col IN
            (
              SELECT ...
            )

        Falls back to the base generator for IN with a value list.
        """
        query = expression.args.get("query")
        if self.pretty and query is not None:
            this = self.sql(expression, "this")
            compact = self._compact_sql(query.this)
            # A commented subquery can't go on one line (a -- comment would
            # swallow the rest of it).
            if not self._has_comments(query) and not self.too_wide([f"{this} IN ({compact})"]):
                return f"{this} IN ({compact})"
            select_sql = self.sql(query.this)
            indented = self.indent(select_sql)
            return f"{this} IN\n(\n{indented}\n)"
        return super().in_sql(expression)

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
                self._as_align_width = self._compute_as_align_width(payload_expressions, prefix_width=self.pad + 4)
            try:
                payload = self.expressions(expression, key=key, indent=False)
            finally:
                self._as_align_width = saved_align
            if not payload:
                continue
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
    # ------------------------------------------------------------------

    def not_sql(self, expression: exp.Not) -> str:
        inner = expression.this
        if isinstance(inner, exp.Is) and isinstance(inner.expression, exp.Null):
            # A trailing comment after NULL is attached to the Null node, which
            # this shortcut never renders, so carry its comments over.
            comments = [*(inner.comments or []), *(inner.expression.comments or [])]
            return self.maybe_comment(f"{self.sql(inner.this)} IS NOT NULL", comments=comments)
        return f"NOT {self.sql(expression, 'this')}"

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
            # correctly. Explicit joins (INNER, LEFT, SEMI, etc.) are excluded
            # because sqlglot re-parses `FROM t JOIN u` differently from
            # `SELECT * FROM t JOIN u`, breaking idempotency.
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
                and only_comma_joins
            ):
                expr_copy = expression.copy()
                expr_copy.set("expressions", [])
                sql = super().select_sql(expr_copy)
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
        return super().order_sql(expression, flat=flat)

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
    # ORDER BY inside the aggregate is rendered compactly (non-pretty)
    # to keep it inline: STRING_AGG(x, ', ' ORDER BY x).
    # ------------------------------------------------------------------

    def groupconcat_sql(self, expression: exp.GroupConcat) -> str:
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
        # Non-DISTINCT, compact mode, or DISTINCT that fits inline: emit list(<inner>)
        inner = self.sql(expression, "this")
        if self.pretty and self._has_comments(expression.this):
            # e.g. list(x ORDER BY y -- note): put the argument on its own line
            inner = self._wrapped_args([inner])
        result = f"{func_name}({inner})"
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
        arg_sqls = tuple(self.sql(arg) for arg in args if arg is not None and not isinstance(arg, bool))
        if self.pretty and (self.too_wide(arg_sqls) or self._has_commented_arg(args, sep)):
            return self._wrapped_args(arg_sqls, sep=sep)
        return sep.join(arg_sqls)

    def _has_commented_arg(self, args: t.Sequence[t.Any], sep: str) -> bool:
        """A commented argument wraps the call one argument per line, so its
        -- comment ends the line instead of swallowing the rest of the call."""
        return sep.strip() == "," and any(isinstance(a, exp.Expr) and self._has_comments(a) for a in args)

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
