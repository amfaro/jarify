"""Custom DuckDB SQL generator with full control over formatting style.

Subclasses sqlglot's DuckDBGenerator to enforce jarify's opinionated rules:
- Configurable indentation width
- Leading-comma style: ,col aligned with content at pad+1
- Bare JOIN → INNER JOIN normalization
- AND/OR conditions always on separate lines in pretty mode
- WHERE/HAVING/ON: first condition inline with keyword, AND/OR right-justified
  so all condition content aligns at the same column
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
from sqlglot.dialects.duckdb import DuckDB

if TYPE_CHECKING:
    from jarify.config import JarifyConfig


class JarifyGenerator(DuckDB.Generator):
    """Opinionated DuckDB SQL generator for jarify."""

    # DuckDB's TRANSFORMS maps exp.Pivot to a preprocess([unqualify_columns]) transform,
    # which strips all table qualifiers from columns inside PIVOT subqueries.
    # We remove it so the dispatch falls through to pivot_sql directly, preserving qualifiers.
    TRANSFORMS: ClassVar[dict] = {k: v for k, v in DuckDB.Generator.TRANSFORMS.items() if k is not exp.Pivot}

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
                "bool_and",               # LogicalAnd
                "bool_or",                # LogicalOr
                "boolxor",                # BoolxorAgg
                "json_arrayagg",          # JSONArrayAgg
                "json_group_object",      # JSONObjectAgg / JSONBObjectAgg
                "listagg",                # GroupConcat
                "quantile_cont",          # PercentileCont
                "quantile_disc",          # PercentileDisc
                "var_pop",                # VariancePop
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
        self._join_alias_col: int | None = None   # set during FROM/JOIN block rendering

    # ------------------------------------------------------------------
    # Function name casing: aggregates/window functions → UPPER, rest → lower
    # ------------------------------------------------------------------

    def normalize_func(self, name: str) -> str:
        return name.upper() if name.lower() in self._UPPERCASE_FUNCS else name.lower()

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
        if not (self.pretty and self.leading_comma):
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
                comments = self.maybe_comment("", e) if isinstance(e, exp.Expr) else ""
                # First item gets one extra leading space (aligns content with ,item lines)
                leader = " " if i == 0 else ","
                result_sqls.append(f"{leader}{prefix}{sql}{comments}")
        finally:
            self._as_align_width = saved_align

        result_sql = "\n".join(s.rstrip() for s in result_sqls)
        return self.indent(result_sql, skip_first=skip_first, skip_last=skip_last) if indent else result_sql

    def _compute_as_align_width(self, expressions_list: list) -> int | None:
        """Compute the column width for AS alignment in a SELECT expression list.

        Returns None if alignment should not be applied (< 2 aliases, or any
        aliased column expression spans multiple lines).
        """
        aliased = [e for e in expressions_list if isinstance(e, exp.Alias)]
        if len(aliased) < 2:
            return None

        col_widths: list[int] = []
        for a in aliased:
            col_sql = self.sql(a.this)
            if "\n" in col_sql:
                # Multi-line expression — skip alignment for the whole SELECT
                return None
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

    def cte_sql(self, expression: exp.CTE) -> str:
        alias = expression.args.get("alias")
        if alias:
            alias.add_comments(expression.pop_comments())
        alias_sql = self.sql(expression, "alias")
        # Put the opening paren on its own line: alias AS\n(...)
        return f"{alias_sql} AS\n{self.wrap(expression)}"

    def with_sql(self, expression: exp.With) -> str:
        ctes = expression.expressions
        if not ctes:
            return ""
        recursive = "RECURSIVE " if self.CTE_RECURSIVE_KEYWORD_REQUIRED and expression.args.get("recursive") else ""
        parts = [f"WITH {recursive}{self.cte_sql(ctes[0])}"]
        for cte in ctes[1:]:
            parts.append(f",{self.cte_sql(cte)}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # JOIN normalization: bare JOIN → INNER JOIN; LEFT/RIGHT OUTER → LEFT/RIGHT
    # ------------------------------------------------------------------

    def join_sql(self, expression: exp.Join) -> str:
        if not expression.side and not expression.kind and not expression.method:
            # Bare JOIN with no qualifier — normalize to INNER JOIN
            expression = expression.copy()
            expression.set("kind", "INNER")
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
        if not self.pretty or not isinstance(table, exp.Table):
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

    def _table_ref_only_sql(self, table_expr: exp.Expression) -> str | None:
        """Return the table reference string (no alias) for simple tables, else None."""
        if isinstance(table_expr, exp.Table):
            ref = self.table_parts(table_expr)
            return None if "\n" in ref else ref
        return None

    def _compute_join_align_width(self, expression: exp.Select) -> int | None:
        """Compute the right-alignment column for the FROM/JOIN block.

        Returns `max(kw_len + 1 + table_len + alias_len) + 1` across all aliased
        entries, so that the END of every alias lands at the same column (one space
        before the ON/USING keyword or end of line).  Returns None when alignment
        should be skipped (any entry uses a subquery, or no entries have aliases).
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
    # WHERE / HAVING: first condition inline, AND/OR right-justified
    # ------------------------------------------------------------------

    def where_sql(self, expression: exp.Where) -> str:
        return self._inline_clause_sql("WHERE", expression)

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
                # Continuation lines inside parens: add one pad level so they
                # stay more indented than the AND/OR line that opened them.
                result.append(f"{' ' * self.pad}{line}")
            depth += line.count("(") - line.count(")")

        return self.seg("\n".join(result))

    # ------------------------------------------------------------------
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
            if (
                self._config.prefer_from_first
                and len(exprs) == 1
                and isinstance(exprs[0], exp.Star)
                and not expression.args.get("distinct")
                and not expression.args.get("joins")
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
        return super().datatype_sql(expression).lower()

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
