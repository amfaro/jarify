"""Rule: flag CROSS JOINs with WHERE clause that connects multiple tables."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import LintOnlyRule, _node_pos
from jarify.types import LintViolation


def _extract_table_refs(expr: exp.Expression) -> set[str | None]:
    """Extract all table references from an expression (qualified column names)."""
    tables = set()
    for col in expr.find_all(exp.Column):
        # Get the table part of a qualified column (e.g., 'a' from 'a.id')
        if col.table:
            tables.add(col.table)
        else:
            # Unqualified column; treat as potentially cross-table
            tables.add(None)
    return tables


def _is_join_condition(expr: exp.Expression) -> bool:
    """
    Check if an expression is a join condition (equality between columns from different tables).
    Returns True if expr is `col1 = col2` where col1 and col2 have different table refs.
    """
    if not isinstance(expr, exp.EQ):
        return False
    left_tables = _extract_table_refs(expr.left)
    right_tables = _extract_table_refs(expr.right)
    # A join condition connects different tables
    # (Ignore None entries for unqualified columns)
    left_named = {t for t in left_tables if t is not None}
    right_named = {t for t in right_tables if t is not None}
    if not left_named or not right_named:
        return False
    # Check if left and right reference different tables
    return bool(left_named & right_named == set())  # No overlap = different tables


def _has_join_condition_in_where(where: exp.Expression) -> bool:
    """Check if WHERE clause contains a join condition (connecting multiple tables)."""
    if not where:
        return False
    # Extract the actual condition from the WHERE wrapper (Where.this)
    condition_expr = where.this if isinstance(where, exp.Where) else where
    if not condition_expr:
        return False
    # Flatten AND conditions
    return any(_is_join_condition(condition) for condition in _flatten_and(condition_expr))


def _flatten_and(node: exp.Expression) -> list[exp.Expression]:
    """Flatten a nested AND chain into a flat list of individual conditions."""
    if isinstance(node, exp.And):
        return _flatten_and(node.left) + _flatten_and(node.right)
    return [node]


class CrossJoinWithWhereConditionRule(LintOnlyRule):
    """Lint: flag CROSS JOINs with WHERE clause connecting multiple tables.

    A CROSS JOIN with a WHERE clause that connects columns from different tables
    should be rewritten as an INNER JOIN with an ON clause.
    """

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "cross-join-with-where-condition"

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for select in tree.find_all(exp.Select):
            if not self.enabled_for_node(select):
                continue

            # Check if this SELECT has a CROSS JOIN
            has_cross_join = False
            for join in select.find_all(exp.Join):
                # Check if it's a CROSS JOIN (explicit) or comma join (implicit)
                is_cross = join.args.get("kind") == "CROSS" or (
                    not join.args.get("kind")
                    and not join.args.get("side")
                    and not join.args.get("on")
                    and not join.args.get("using")
                )
                if is_cross:
                    has_cross_join = True
                    break

            if not has_cross_join:
                continue

            # Check if there's a WHERE clause with join conditions
            where = select.args.get("where")
            if _has_join_condition_in_where(where):
                _line, _col = _node_pos(select)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=(
                            "CROSS JOIN with WHERE clause connecting multiple tables; "
                            "rewrite as INNER JOIN with ON clause"
                        ),
                        line=_line,
                        column=_col,
                    )
                )

        return violations
