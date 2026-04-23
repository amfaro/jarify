"""Rule: auto-rewrite implicit cross joins to CROSS JOIN; warn when linting."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation


def _is_comma_join(join: exp.Join) -> bool:
    return (
        not join.args.get("kind")
        and not join.args.get("side")
        and not join.args.get("on")
        and not join.args.get("using")
        and not join.args.get("method")
    )


class NoImplicitCrossJoinRule(FormatterRule):
    """Rewrite comma-joined tables to explicit CROSS JOIN; flag in lint output."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "no-implicit-cross-join"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        for join in tree.find_all(exp.Join):
            if _is_comma_join(join):
                join.set("kind", "CROSS")
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for join in tree.find_all(exp.Join):
            if _is_comma_join(join):
                _line, _col = _node_pos(join)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message="Implicit CROSS JOIN detected; use explicit CROSS JOIN or add an ON/USING clause",
                        line=_line,
                        column=_col,
                    )
                )
        return violations
