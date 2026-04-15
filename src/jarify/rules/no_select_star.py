"""Rule: warn/error on SELECT * usage."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import LintOnlyRule, _node_pos
from jarify.types import LintViolation


class NoSelectStarRule(LintOnlyRule):
    """Flag SELECT * (or table.*) as a lint violation."""

    def __init__(self, severity: str = "warn", prefer_from_first: bool = False) -> None:
        self.severity = severity
        self.prefer_from_first = prefer_from_first

    @property
    def name(self) -> str:
        return "no-select-star"

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
                select = parent if isinstance(parent, exp.Select) else parent.parent
                # When prefer_from_first is on, SELECT * FROM t gets rewritten to
                # FROM t by the formatter. Linting the formatted output (FROM t)
                # would re-parse to the same AST, so skip single-table star selects
                # that the formatter already handles via FROM-first syntax.
                if (
                    self.prefer_from_first
                    and len(select.expressions) == 1
                    and isinstance(select.expressions[0], exp.Star)
                    and not select.args.get("distinct")
                    and not select.args.get("joins")
                ):
                    continue
                _line, _col = _node_pos(star)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        message="Avoid SELECT *; list columns explicitly",
                        severity=self.severity,
                        line=_line,
                        column=_col,
                    )
                )
        return violations
