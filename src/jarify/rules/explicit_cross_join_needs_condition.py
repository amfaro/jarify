"""Rule: flag explicit CROSS JOINs without ON/USING clause."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import LintOnlyRule, _node_pos
from jarify.types import LintViolation


class ExplicitCrossJoinNeedsConditionRule(LintOnlyRule):
    """Lint: flag explicit CROSS JOIN without a join condition (ON/USING clause)."""

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "explicit-cross-join-needs-condition"

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for join in tree.find_all(exp.Join):
            if not self.enabled_for_node(join):
                continue
            # Check if it's an explicit CROSS JOIN
            if join.args.get("kind") != "CROSS":
                continue
            # Check if it has no ON or USING clause
            if join.args.get("on") or join.args.get("using"):
                continue

            # Violation found: explicit CROSS JOIN without join condition
            _line, _col = _node_pos(join)
            message = (
                "Explicit CROSS JOIN without join condition (ON/USING clause); "
                "consider adding a join condition or use a different join type"
            )
            violations.append(
                LintViolation(
                    rule=self.name,
                    severity=self.severity,
                    message=message,
                    line=_line,
                    column=_col,
                )
            )

        return violations
