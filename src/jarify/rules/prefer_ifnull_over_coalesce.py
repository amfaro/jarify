"""Rule: prefer `ifnull(x, y)` over two-argument `coalesce(x, y)`."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation


class PreferIfnullOverCoalesceRule(FormatterRule):
    """Format and lint: rewrite two-argument COALESCE calls to IFNULL()."""

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-ifnull-over-coalesce"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        for coalesce in tree.find_all(exp.Coalesce):
            if len(coalesce.expressions) != 1 or not self.enabled_for_node(coalesce):
                continue
            replacement = exp.Anonymous(
                this="ifnull",
                expressions=[coalesce.this.copy(), coalesce.expressions[0].copy()],
            )
            coalesce.replace(replacement)
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []

        violations: list[LintViolation] = []
        for coalesce in tree.find_all(exp.Coalesce):
            if len(coalesce.expressions) != 1 or not self.enabled_for_node(coalesce):
                continue
            line, col = _node_pos(coalesce)
            violations.append(
                LintViolation(
                    rule=self.name,
                    severity=self.severity,
                    message="Two-argument COALESCE can be rewritten as ifnull(x, y)",
                    line=line,
                    column=col,
                )
            )
        return violations
