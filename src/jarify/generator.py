"""Custom DuckDB SQL generator with full control over formatting style.

Subclasses sqlglot's DuckDBGenerator to enforce jarify's opinionated rules:
- Configurable indentation width
- Configurable comma placement (trailing vs leading)
- Bare JOIN → INNER JOIN normalization
- AND/OR conditions always on separate lines in pretty mode
- Consistent keyword casing
"""

from __future__ import annotations

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
            max_text_width=config.max_line_length,
            comments=True,
        )
        self._config = config

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

        # Collect all terms from the connector chain
        terms: list[str] = []
        ops: list[str] = []
        self._flatten_connector(expression, terms, ops)

        if not terms:
            return super().connector_sql(expression, op)

        if self.pretty:
            # Always put each condition on its own line
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
