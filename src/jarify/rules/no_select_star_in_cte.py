"""Rule: flag SELECT * inside CTE body definitions."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import LintOnlyRule, _node_pos
from jarify.types import LintViolation


class NoSelectStarInCteRule(LintOnlyRule):
    """Lint: flag SELECT * used inside a CTE body (stricter than no-select-star)."""

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "no-select-star-in-cte"

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        with_clause = tree.args.get("with_")
        if not with_clause:
            return []

        for cte in with_clause.expressions:
            cte_name = cte.alias or "<unnamed>"
            for star in cte.this.find_all(exp.Star):
                parent = star.parent
                if isinstance(parent, exp.Select) or (
                    isinstance(parent, exp.Column) and isinstance(parent.parent, exp.Select)
                ):
                    if not self.enabled_for_node(star):
                        continue
                    _line, _col = _node_pos(star)
                    violations.append(
                        LintViolation(
                            rule=self.name,
                            severity=self.severity,
                            message=f"Avoid SELECT * inside CTE '{cte_name}'; list columns explicitly",
                            line=_line,
                            column=_col,
                        )
                    )

        return violations
