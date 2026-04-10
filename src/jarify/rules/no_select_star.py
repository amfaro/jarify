"""Rule: warn/error on SELECT * usage."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class NoSelectStarRule(FormatterRule):
    """Flag SELECT * (or table.*) as a lint violation."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "no-select-star"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for star in tree.find_all(exp.Star):
            parent = star.parent
            # Only flag stars directly in SELECT expressions, not COUNT(*)
            if isinstance(parent, exp.Select) or (
                isinstance(parent, exp.Column) and isinstance(parent.parent, exp.Select)
            ):
                violations.append(
                    LintViolation(
                        rule=self.name,
                        message="Avoid SELECT *; list columns explicitly",
                        severity=self.severity,
                        line=getattr(star, "line", None),
                        column=getattr(star, "col", None),
                    )
                )
        return violations
