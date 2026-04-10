"""Rule: recommend QUALIFY clause over subquery-based window function filtering.

Pattern to flag:
  SELECT * FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn FROM t) WHERE rn = 1

Suggest:
  SELECT ..., ROW_NUMBER() OVER (...) AS rn FROM t QUALIFY rn = 1
"""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class DuckdbPreferQualifyRule(FormatterRule):
    """Lint: suggest QUALIFY instead of filtering on a window function in a subquery."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "duckdb-prefer-qualify"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        # Look for: SELECT ... FROM (subquery with window functions) WHERE <alias> = <literal>
        for select in tree.find_all(exp.Select):
            where = select.args.get("where")
            if not where:
                continue
            from_clause = select.args.get("from_")
            if not from_clause:
                continue
            source = from_clause.this
            if not isinstance(source, exp.Subquery):
                continue
            inner = source.this
            if not isinstance(inner, exp.Select):
                continue
            # Does the inner query have window functions?
            has_window = any(True for _ in inner.find_all(exp.Window))
            if has_window:
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=("Consider using QUALIFY instead of a subquery to filter window function results"),
                    )
                )
        return violations
