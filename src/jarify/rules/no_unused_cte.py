"""Rule: warn/error on CTEs that are defined but never referenced."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class NoUnusedCteRule(FormatterRule):
    """Flag CTEs (WITH clause entries) that are never referenced in the query body."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "no-unused-cte"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        with_clause = tree.args.get("with_")
        if not with_clause:
            return []

        cte_names = {cte.alias.lower() for cte in with_clause.expressions if cte.alias}

        # Collect all table references in the query body (excluding the CTE definitions themselves)
        referenced: set[str] = set()
        body = tree.copy()
        body.set("with_", None)
        for table in body.find_all(exp.Table):
            referenced.add(table.name.lower())

        # Also check cross-CTE references (a CTE can reference an earlier CTE)
        for cte in with_clause.expressions:
            for table in cte.this.find_all(exp.Table):
                referenced.add(table.name.lower())

        for name in cte_names:
            if name not in referenced:
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=f"CTE '{name}' is defined but never referenced",
                    )
                )
        return violations
