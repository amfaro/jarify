"""Custom DuckDB SQL generator with full control over formatting style.

Subclasses sqlglot's DuckDBGenerator to enforce jarify's opinionated rules:
- Configurable indentation width
- Leading-comma style: ,col aligned with content at pad+1
- Bare JOIN → INNER JOIN normalization
- AND/OR conditions always on separate lines in pretty mode
- CTE: opening paren on its own line, comma-prefix separator
- Consistent keyword casing; DuckDB functions in lowercase
- IS NOT NULL preserved (not rewritten to NOT x IS NULL)
- NULLS LAST/FIRST suppressed when it matches DuckDB's default
- Column aliases aligned on AS when 2+ aliases exist in a SELECT
"""

from __future__ import annotations

import typing as t
from typing import TYPE_CHECKING

import sqlglot.expressions as exp
from sqlglot.dialects.duckdb import DuckDB

if TYPE_CHECKING:
    from jarify.config import JarifyConfig


class JarifyGenerator(DuckDB.Generator):
    """Opinionated DuckDB SQL generator for jarify."""

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
    # JOIN normalization: bare JOIN → INNER JOIN
    # ------------------------------------------------------------------

    def join_sql(self, expression: exp.Join) -> str:
        if not expression.side and not expression.kind and not expression.method:
            # Bare JOIN with no qualifier — normalize to INNER JOIN
            expression = expression.copy()
            expression.set("kind", "INNER")
        return super().join_sql(expression)

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

    def format_args(self, *args: t.Any, sep: str = ", ") -> str:
        arg_sqls = tuple(self.sql(arg) for arg in args if arg is not None and not isinstance(arg, bool))
        if self.pretty and self.too_wide(arg_sqls):
            if self.leading_comma:
                parts = [f" {arg_sqls[0]}"]
                parts.extend(f",{sql}" for sql in arg_sqls[1:])
                return self.indent("\n" + "\n".join(parts) + "\n", skip_first=True, skip_last=True)
            return self.indent("\n" + f"{sep.strip()}\n".join(arg_sqls) + "\n", skip_first=True, skip_last=True)
        return sep.join(arg_sqls)
