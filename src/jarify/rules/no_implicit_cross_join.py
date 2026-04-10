"""Rule: warn/error on implicit cross joins (comma-separated FROM)."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class NoImplicitCrossJoinRule(FormatterRule):
    """Flag comma-separated tables in FROM (implicit CROSS JOIN)."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "no-implicit-cross-join"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for join in tree.find_all(exp.Join):
            # sqlglot represents comma joins as Join nodes with no kind/side/on
            if (
                not join.args.get("kind")
                and not join.args.get("side")
                and not join.args.get("on")
                and not join.args.get("using")
                and not join.args.get("method")
            ):
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=(
                            "Implicit CROSS JOIN detected; use explicit CROSS JOIN or add an ON/USING clause"
                        ),
                    )
                )
        return violations
