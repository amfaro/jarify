"""Rule: CTE names must start with an underscore."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class CteNamingRule(FormatterRule):
    """Lint: CTE names must begin with an underscore (e.g. _people)."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "cte-naming"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        with_clause = tree.args.get("with_")
        if not with_clause:
            return []
        for cte in with_clause.expressions:
            if cte.alias and not cte.alias.startswith("_"):
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=f"CTE '{cte.alias}' should start with an underscore (e.g. '_{cte.alias}')",
                    )
                )
        return violations
