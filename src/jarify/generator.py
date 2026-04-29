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
- Struct tuple casts (val, ...)::type use leading-comma style when multi-line
- DISTINCT inside aggregates appears on its own line when the call wraps
- CREATE TABLE: opening paren on its own line, column name/type alignment,
  blank line before table-level constraints
- Aggregate and window functions (COUNT, SUM, ROW_NUMBER, RANK, …) are uppercase;
  all other DuckDB built-in functions remain lowercase
- FROM/JOIN block: AS omitted from table aliases; ON/USING inline; aliases
  column-aligned when the block contains only simple (single-line) table refs
"""

from __future__ import annotations

import re
import typing as t
from typing import TYPE_CHECKING, ClassVar

import sqlglot.expressions as exp
from sqlglot.dialects.dialect import groupconcat_sql as _groupconcat_sql
from sqlglot.dialects.duckdb import DuckDB

if TYPE_CHECKING:
    from jarify.config import JarifyConfig


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
        self._col_name_align: int | None = None  # set during CREATE TABLE column rendering
        self._col_type_align: int | None = None  # set during CREATE TABLE column rendering
        self._join_alias_col: int | None = None  # set during FROM/JOIN block rendering
        self._leading_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()
        self._trailing_sep_comment_texts: frozenset[str] = frozenset()  # set by formatter before generate()

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
            self._as_align_width = self._compute_as_align_width(list(expressions_list))

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
        if dynamic and not self.too_wide(result_sqls):
            return sep.join(s.lstrip(",").lstrip() for s in result_sqls)
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
            parts.append(f"/*{c}*/" if "\n" in c else f"-- {c.strip()}")
        if not parts:
            return ""
        if leading:
            return "\n".join(parts)
        return " " + " ".join(parts)

    def _compute_as_align_width(self, expressions_list: list) -> int | None:
        """Compute the column width for AS alignment in a SELECT expression list.

        Returns None if alignment should not be applied (< 2 aliases, or any
        aliased column expression spans multiple lines).
        """
        aliased = [e for e in expressions_list if isinstance(e, exp.Alias)]
        if len(aliased) < 2:
            return None

        col_widths: list[int] = []
        for e in expressions_list:
            if isinstance(e, exp.Alias):
                col_sql = self.sql(e.this)
                if "\n" in col_sql:
                    # Multi-line aliased expression — skip alignment for the whole SELECT
                    return None
                col_widths.append(len(col_sql))
            else:
                # Non-aliased columns count toward the alignment width so AS
                # keywords clear the longest expression in the list.
                col_sql = self.sql(e)
                if "\n" not in col_sql:
                    col_widths.append(len(col_sql))

        return max(col_widths)

    # ------------------------------------------------------------------
    # Alias: align AS keyword when _as_align_width is set
    # ------------------------------------------------------------------

    def alias_sql(self, expression: exp.Alias) -> str:
        this_sql = self.sql(expression, "this")
        alias_name = self.sql(expression, "alias")
        if not alias_name:
            return this_sql
        align_width = self._as_align_width
        if align_width is not None and isinstance(expression.parent, exp.Select):
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

        trail_parts: list[str] = []
        for c in trail:
            text = c.strip()
            if text:
                trail_parts.append(f"/*{c}*/" if "\n" in c else f"-- {text}")
        comment_suffix = (" " + " ".join(trail_parts)) if trail_parts else ""
        body = f"{alias_sql} AS{comment_suffix}\n{self.wrap(expression)}"

        if lead:
            prefix = "\n".join(f"-- {c.strip()}" for c in lead if c.strip())
            return f"{prefix}\n{body}"
        return body

    def with_sql(self, expression: exp.With) -> str:
        ctes = expression.expressions
        if not ctes:
            return ""
        recursive = "RECURSIVE " if self.CTE_RECURSIVE_KEYWORD_REQUIRED and expression.args.get("recursive") else ""

        def _entry(cte: exp.CTE, sep: str) -> str:
            rendered = self.cte_sql(cte)
            if not rendered.startswith("--"):
                return sep + rendered
            # Leading comment lines must appear before the separator
            lines = rendered.split("\n")
            comment_lines, body_lines = [], []
            for line in lines:
                if not body_lines and line.startswith("--"):
                    comment_lines.append(line)
                else:
                    body_lines.append(line)
            return "\n".join(comment_lines) + "\n" + sep + "\n".join(body_lines)

        parts = [_entry(ctes[0], f"WITH {recursive}")]
        for cte in ctes[1:]:
            parts.append(_entry(cte, ","))
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # JOIN normalization: bare JOIN → INNER JOIN; LEFT/RIGHT OUTER → LEFT/RIGHT
    # ------------------------------------------------------------------

    def join_sql(self, expression: exp.Join) -> str:
        has_condition = expression.args.get("on") or expression.args.get("using")
        if not expression.side and not expression.kind and not expression.method:
            if has_condition:
                # Bare JOIN with a condition — normalize to INNER JOIN
                expression = expression.copy()
                expression.set("kind", "INNER")
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
        on_sql = self._inline_on_sql(expression)

        if self._join_alias_col is not None and isinstance(this, exp.Table):
            table_ref = self.table_parts(this)
            alias_str = self._table_alias_str(this)
            if alias_str:
                pad = " " * max(1, self._join_alias_col - len(op_sql) - 1 - len(table_ref) - len(alias_str))
                return self.seg(f"{op_sql} {table_ref}{pad}{alias_str}{on_sql}")
            return self.seg(f"{op_sql} {table_ref}{on_sql}")

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
                return self.seg(f"{op_sql} {unnest_ref}{pad}{full_alias}{on_sql}")

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

        return self.seg(f"{op_sql} {this_sql}{on_sql}")

    def from_sql(self, expression: exp.From) -> str:
        table = expression.this
        if not self.pretty:
            return super().from_sql(expression)

        if isinstance(table, exp.Subquery):
            # Render compactly; non-pretty seg() prepends a space, so strip it.
            compact = self._compact_sql(expression).strip()
            if not self.too_wide([compact]):
                return self.seg(compact)
            return super().from_sql(expression)

        if not isinstance(table, exp.Table):
            return super().from_sql(expression)

        alias_str = self._table_alias_str(table)
        if not alias_str:
            return super().from_sql(expression)

        table_ref = self.table_parts(table)
        if self._join_alias_col is not None:
            pad = " " * max(1, self._join_alias_col - len("FROM") - 1 - len(table_ref) - len(alias_str))
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

    def _inline_on_sql(self, expression: exp.Join) -> str:
        """Render the ON or USING clause as a single inline string."""
        on_expr = expression.args.get("on")
        using = expression.args.get("using")
        if on_expr:
            saved = self.pretty
            self.pretty = False
            try:
                on_rendered = self.sql(on_expr)
            finally:
                self.pretty = saved
            return f" ON {on_rendered}"
        if using:
            cols = ", ".join(self.sql(col) for col in using)
            return f" USING ({cols})"
        return ""

    def _entry_alias_str(self, table_expr: exp.Expression) -> str:
        """Return the rendered alias string for a FROM/JOIN entry (Table or Unnest)."""
        if isinstance(table_expr, exp.Table):
            return self._table_alias_str(table_expr)
        if isinstance(table_expr, exp.Unnest):
            alias_node = table_expr.args.get("alias")
            return self.sql(alias_node) if alias_node else ""
        return ""

    def _table_ref_only_sql(self, table_expr: exp.Expression) -> str | None:
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
        """Compute the start-alignment column for aliases in the FROM/JOIN block.

        Returns `max(kw_len + 1 + ref_len) + 1` across all aliased entries so
        that every alias STARTS at the same column regardless of its own length.
        Returns None when alignment should be skipped (any entry uses a
        subquery, or no entries have aliases).
        """
        from_expr = expression.args.get("from_")
        joins = expression.args.get("joins") or []
        if not from_expr:
            return None

        entries: list[tuple[int, str, exp.Expression]] = []

        from_ref = self._table_ref_only_sql(from_expr.this)
        if from_ref is None:
            return None
        entries.append((len("FROM"), from_ref, from_expr.this))

        for join in joins:
            # Normalize OUTER before measuring keyword length so the alignment
            # width matches what join_sql actually renders.  For example,
            # LEFT OUTER JOIN (15 chars) is rendered as LEFT JOIN (9 chars),
            # so we must use the post-normalization keyword here.
            if join.side in ("LEFT", "RIGHT") and join.kind == "OUTER":
                normalized = join.copy()
                normalized.set("kind", None)
                kw = self._join_keyword(normalized)
            else:
                kw = self._join_keyword(join)
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
                    max_total = max(max_total, kw_len + 1 + len(ref) + len(alias))
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
    # Connector: always break AND/OR onto separate lines in pretty mode
    # ------------------------------------------------------------------

    def connector_sql(
        self,
        expression: exp.Connector,
        op: str,
        stack: list[str | exp.Expr] | None = None,
    ) -> str:
        if stack is not None:
            return super().connector_sql(expression, op, stack)

        terms: list[str] = []
        ops: list[str] = []
        self._flatten_connector(expression, terms, ops)

        if not terms:
            return super().connector_sql(expression, op)

        if self.pretty:
            lines = [terms[0]]
            for connector_op, term in zip(ops, terms[1:], strict=False):
                lines.append(f"{connector_op} {term}")
            return "\n".join(lines)

        return f" {op} ".join(terms)

    def _flatten_connector(
        self,
        node: exp.Expression,
        terms: list[str],
        ops: list[str],
    ) -> None:
        """Recursively flatten a nested AND/OR chain into a flat list."""
        if isinstance(node, exp.Connector):
            op_name = "AND" if isinstance(node, exp.And) else "OR"
            self._flatten_connector(node.left, terms, ops)
            ops.append(op_name)
            self._flatten_connector(node.right, terms, ops)
        else:
            terms.append(self.sql(node))

    # ------------------------------------------------------------------
    # Paren: keep inline when the content fits within max_line_length
    # ------------------------------------------------------------------

    def paren_sql(self, expression: exp.Paren) -> str:
        if not self.pretty:
            return super().paren_sql(expression)
        compact = self._compact_sql(expression.this)
        if not self.too_wide([f"({compact})"]):
            return f"({compact})"
        return super().paren_sql(expression)

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

        inline = f"if({', '.join(compact_args)})"
        if not self.too_wide([inline]):
            return inline

        branch_sqls = [compact_cond]
        branch_sqls.append(compact_then if not self.too_wide([compact_then]) else self.sql(true_expr))
        if false_expr is not None:
            compact_false = self._compact_sql(false_expr)
            branch_sqls.append(compact_false if not self.too_wide([compact_false]) else self.sql(false_expr))

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
    # CASE: keep WHEN/THEN on one line; align THEN across branches;
    # compact THEN/ELSE values so OR/AND chains don't expand.
    # ------------------------------------------------------------------

    def case_sql(self, expression: exp.Case) -> str:
        this = self.sql(expression, "this")

        when_parts: list[str] = []
        then_parts: list[str] = []
        for e in expression.args["ifs"]:
            wp_expr = e.args.get("this")
            wp = self._compact_sql(wp_expr) if wp_expr is not None else self.sql(e, "this")
            true_expr = e.args.get("true")
            if self.pretty and true_expr is not None:
                compact = self._compact_sql(true_expr)
                tp = compact if not self.too_wide([f"WHEN {wp} THEN {compact}"]) else self.sql(e, "true")
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

        def _build(align: bool) -> list[str]:
            max_w = max((len(w) for w in when_parts), default=0) if align else 0
            stmts = [f"CASE {this}" if this else "CASE"]
            for wp, tp in zip(when_parts, then_parts, strict=True):
                stmts.append(f"WHEN {wp.ljust(max_w)} THEN {tp}")
            if default_sql is not None:
                stmts.append(f"ELSE {default_sql}")
            stmts.append("END")
            return stmts

        compact_stmts = _build(align=False)
        compact_inline = " ".join(compact_stmts)
        # In pretty mode, always emit multi-line — every WHEN/ELSE branch on its
        # own line. Inline only in non-pretty (e.g. compact sub-expression) mode.
        if not self.pretty:
            return compact_inline

        # Multi-line: align THEN when all branches have single-line THEN values
        align = len(when_parts) >= 2 and all("\n" not in tp for tp in then_parts)
        return self.indent("\n".join(_build(align=align)), skip_first=True, skip_last=True)

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

        conditions = self._flatten_and(expression.this)

        # Max EQ LHS width across top-level AND operands only — nested EQs (inside
        # Paren, subqueries, etc.) must not influence padding of sibling conditions.
        eq_lhs_widths = [len(self.sql(cond.this)) for cond in conditions if isinstance(cond, exp.EQ)]
        # Only align when there are at least 2 top-level EQ comparisons
        target = (max(eq_lhs_widths) + 1) if len(eq_lhs_widths) >= 2 else 0

        result: list[str] = []
        for i, cond in enumerate(conditions):
            if target > 0 and isinstance(cond, exp.EQ):
                lhs = self.sql(cond.this)
                rhs = self.sql(cond.expression)
                cond_str = f"{lhs.ljust(target)}= {rhs}" if "\n" not in lhs else self.sql(cond)
            else:
                cond_str = self._compact_sql(cond) if isinstance(cond, exp.Paren) else self.sql(cond)

            if i == 0:
                result.append(f"WHERE {cond_str}")
            else:
                result.append(f"  AND {cond_str}")

        return self.seg("\n".join(result))

    def _flatten_and(self, condition: exp.Expression) -> list[exp.Expression]:
        """Return the flat list of operands from a nested AND chain."""
        if isinstance(condition, exp.And):
            return self._flatten_and(condition.this) + self._flatten_and(condition.expression)
        return [condition]

    def _compact_sql(self, expression: exp.Expression) -> str:
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

    def _inline_clause_sql(self, keyword: str, expression: exp.Expression) -> str:
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
        this = expression.this
        if isinstance(this, exp.Connector):
            terms_temp: list[str] = []
            ops_list: list[str] = []
            self._flatten_connector(this, terms_temp, ops_list)
            if len(set(ops_list)) <= 1:
                compact = self._compact_sql(this)
                if not self.too_wide([f"{keyword} {compact}"]):
                    return self.seg(f"{keyword} {compact}")

        condition_sql = self.sql(expression, "this")
        lines = condition_sql.split("\n")

        keyword_width = len(keyword) + 1  # e.g. 6 for "WHERE "
        result: list[str] = []
        depth = 0

        for i, line in enumerate(lines):
            if i == 0:
                result.append(f"{keyword} {line}")
            elif depth == 0 and line.startswith("AND "):
                prefix = " " * max(0, keyword_width - len("AND "))
                result.append(f"{prefix}{line}")
            elif depth == 0 and line.startswith("OR "):
                prefix = " " * max(0, keyword_width - len("OR "))
                result.append(f"{prefix}{line}")
            else:
                # Pass continuation lines through as-is; child methods (e.g.
                # in_sql) are responsible for their own relative indentation.
                result.append(line)
            depth += line.count("(") - line.count(")")

        return self.seg("\n".join(result))

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
            if not self.too_wide([f"{this} IN ({compact})"]):
                return f"{this} IN ({compact})"
            select_sql = self.sql(query.this)
            indented = self.indent(select_sql)
            return f"{this} IN\n(\n{indented}\n)"
        return super().in_sql(expression)

    # ------------------------------------------------------------------
    # Star: keep * EXCLUDE / REPLACE / RENAME inline when it fits
    # ------------------------------------------------------------------

    def star_sql(self, expression: exp.Star) -> str:
        except_ = self.expressions(expression, key="except_", flat=True)
        replace = self.expressions(expression, key="replace", flat=True)
        rename = self.expressions(expression, key="rename", flat=True)

        except_sql = f" {self.STAR_EXCEPT} ({except_})" if except_ else ""
        replace_sql = f" REPLACE ({replace})" if replace else ""
        rename_sql = f" RENAME ({rename})" if rename else ""

        inline = f"*{except_sql}{replace_sql}{rename_sql}"
        if self.pretty and not self.too_wide([inline]):
            return inline
        return super().star_sql(expression)

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
            return f"{self.sql(inner.this)} IS NOT NULL"
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

            # Detect VALUES-only CTE body: SELECT * FROM (VALUES ...) AS _values
            # sqlglot parses `WITH t(a,b) AS (VALUES ...)` into this shape; render
            # it back to a plain VALUES block instead of FROM (VALUES ...) AS _values.
            if (
                self.pretty
                and self._config.prefer_from_first
                and len(exprs) == 1
                and isinstance(exprs[0], exp.Star)
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
            star = exprs[0] if len(exprs) == 1 and isinstance(exprs[0], exp.Star) else None
            plain_star = star is not None and not any(star.args.get(k) for k in ("except_", "replace", "rename"))
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
    # GROUP BY: one expression per line in pretty mode
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

    # ------------------------------------------------------------------
    # -> / ->>: render without surrounding spaces (value->>'key' not value ->> 'key').
    # sqlglot's default binary() always adds " op " padding; we bypass it here.
    # For simple single-key paths, also strip the $.  prefix that sqlglot adds
    # during AST normalisation ($.offer_key → offer_key), matching DuckDB's
    # short-form syntax.  Complex multi-segment paths keep their $. prefix.
    # ------------------------------------------------------------------

    def jsonextract_sql(self, expression: exp.JSONExtract) -> str:
        return f"{self.sql(expression, 'this')}->{self._json_path_sql(expression.expression)}"

    def jsonextractscalar_sql(self, expression: exp.JSONExtractScalar) -> str:
        return f"{self.sql(expression, 'this')}->>{self._json_path_sql(expression.expression)}"

    def _json_path_sql(self, path_expr: exp.Expression) -> str:
        """Render a JSON path, using bare 'key' for simple root+key paths."""
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
            return _groupconcat_sql(self, expression.copy(), func_name="string_agg", within_group=False)
        finally:
            self.pretty = saved

    # ------------------------------------------------------------------
    # ifnull: prefer ifnull(a, b) over coalesce(a, b) for 2-arg case.
    # 3+ args have no ifnull equivalent so coalesce is kept as-is.
    # Idempotent: formatted ifnull(...) re-enters as exp.Anonymous (masked
    # by the ifnull pre-processor in formatter.py), never hitting this path.
    # ------------------------------------------------------------------

    def coalesce_sql(self, expression: exp.Coalesce) -> str:
        if len(expression.expressions) == 1:
            return self.func("ifnull", expression.this, expression.expressions[0])
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
        return f"{self.sql(expression, 'this')}::{type_sql}"

    # ------------------------------------------------------------------
    # Lambda: wrap body when the flat form exceeds max_line_length
    # ------------------------------------------------------------------

    def lambda_sql(self, expression: exp.Lambda, arrow_sep: str = "->", wrap: bool = True) -> str:
        flat = super().lambda_sql(expression, arrow_sep=arrow_sep, wrap=wrap)
        if not self.pretty:
            return flat
        # Only wrap when the entire lambda string is a single line that exceeds
        # max_line_length.  If the body is already multi-line (e.g. a struct cast
        # that wrapped independently), leave the result as-is — the caller context
        # (format_args) will handle indentation.
        if "\n" in flat or not self.too_wide([flat]):
            return flat
        # Flat single-line lambda is too wide — move the body to its own line,
        # indented one level below the arrow.
        params = self.expressions(expression, flat=True)
        if wrap and len(params.split(",")) > 1:
            params = f"({params})"
        body_sql = self.sql(expression, "this")
        # Indent each body line so it sits beneath the arrow
        indented_body = self.indent(body_sql)
        return f"{params} {arrow_sep}\n{indented_body}"

    # ------------------------------------------------------------------
    # ArrayAgg with DISTINCT: put DISTINCT on its own line when wrapping
    # ------------------------------------------------------------------

    def arrayagg_sql(self, expression: exp.ArrayAgg) -> str:
        if not (self.pretty and isinstance(expression.this, exp.Distinct)):
            return super().arrayagg_sql(expression)
        distinct = expression.this
        exprs_sqls = [self.sql(e) for e in distinct.expressions]
        func_name = self.normalize_func("ARRAY_AGG")
        # Wrap when any expression is already multi-line, or when the flat inline is too wide
        any_multiline = any("\n" in s for s in exprs_sqls)
        flat_inline = f"{func_name}(DISTINCT {', '.join(exprs_sqls)})"
        if not any_multiline and not self.too_wide([flat_inline]):
            return super().arrayagg_sql(expression)
        exprs_str = "\n".join(exprs_sqls)
        inner = self.indent(f"\nDISTINCT {exprs_str}\n", skip_first=True, skip_last=True)
        array_agg_sql = f"{func_name}({inner})"
        return self._add_arrayagg_null_filter(array_agg_sql, expression, expression.this)

    def format_args(self, *args: t.Any, sep: str = ", ") -> str:
        arg_sqls = tuple(self.sql(arg) for arg in args if arg is not None and not isinstance(arg, bool))
        if self.pretty and self.too_wide(arg_sqls):
            if self.leading_comma:
                parts = [f" {arg_sqls[0]}"]
                parts.extend(f",{sql}" for sql in arg_sqls[1:])
                return self.indent("\n" + "\n".join(parts) + "\n", skip_first=True, skip_last=True)
            return self.indent("\n" + f"{sep.strip()}\n".join(arg_sqls) + "\n", skip_first=True, skip_last=True)
        return sep.join(arg_sqls)

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
