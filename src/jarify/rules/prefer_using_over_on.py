"""Rule: suggest USING (col) over ON a.col = b.col for equi-joins."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation


class PreferUsingOverOnRule(FormatterRule):
    """Lint: flag ON a.col = b.col equi-joins where both sides share the same column name."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-using-over-on"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for join in tree.find_all(exp.Join):
            if join.args.get("using"):
                continue
            on = join.args.get("on")
            if not on:
                continue
            # Collect all equality conditions at the top level of the ON clause
            conditions = _flatten_and(on)
            rewritable = []
            for cond in conditions:
                if not isinstance(cond, exp.EQ):
                    continue
                left, right = cond.left, cond.right
                if (
                    isinstance(left, exp.Column)
                    and isinstance(right, exp.Column)
                    and left.name
                    and left.name == right.name
                ):
                    rewritable.append(left.name)

            if rewritable:
                cols = ", ".join(rewritable)
                _line, _col = _node_pos(join)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=(
                            f"ON clause can be simplified to USING ({cols})"
                            " — both sides reference the same column name"
                        ),
                        line=_line,
                        column=_col,
                    )
                )

        return violations


def _flatten_and(node: exp.Expression) -> list[exp.Expression]:
    """Flatten a nested AND chain into a flat list of individual conditions."""
    if isinstance(node, exp.And):
        return _flatten_and(node.left) + _flatten_and(node.right)
    return [node]
