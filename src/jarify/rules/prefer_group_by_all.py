"""Rule: suggest GROUP BY ALL when all non-aggregated SELECT columns are listed."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import LintOnlyRule, _node_pos
from jarify.types import LintViolation


class PreferGroupByAllRule(LintOnlyRule):
    """Lint: flag explicit GROUP BY col list when GROUP BY ALL would be equivalent."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-group-by-all"

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for select in tree.find_all(exp.Select):
            group = select.args.get("group")
            if not group or not group.expressions:
                continue
            if group.args.get("all"):
                # Already GROUP BY ALL — nothing to flag
                continue

            # Collect non-aggregate SELECT expressions (unwrap aliases)
            non_agg_sqls: list[str] = []
            for item in select.expressions:
                inner = item.this if isinstance(item, exp.Alias) else item
                if not inner.find(exp.AggFunc):
                    non_agg_sqls.append(inner.sql(dialect="duckdb"))

            if not non_agg_sqls:
                continue

            group_sqls = {e.sql(dialect="duckdb") for e in group.expressions}
            non_agg_set = set(non_agg_sqls)

            if non_agg_set and non_agg_set == group_sqls:
                _line, _col = _node_pos(group)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message="All non-aggregated SELECT columns are listed in GROUP BY; prefer GROUP BY ALL",
                        line=_line,
                        column=_col,
                    )
                )

        return violations
