"""Rule: rewrite explicit GROUP BY column list to GROUP BY ALL when equivalent."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation

# DuckDB's list() aggregate is parsed by sqlglot as exp.List (Func, not AggFunc).
# Treat it the same as AggFunc when deciding whether a SELECT item is aggregate.
_AGG_TYPES = (exp.AggFunc, exp.List)


def _non_agg_sqls(select: exp.Select) -> set[str]:
    """Return standalone non-aggregate SELECT expressions for GROUP BY ALL.

    Mixed expressions like ``'prefix' || col1 || STRING_AGG(x)`` are excluded
    even though they reference free columns, because DuckDB can reject
    ``GROUP BY ALL`` for that shape with ``Cannot mix aggregates with
    non-aggregated columns!``.
    """
    result: set[str] = set()
    for item in select.expressions:
        inner = item.this if isinstance(item, exp.Alias) else item
        if not inner.find(*_AGG_TYPES):
            result.add(inner.sql(dialect="duckdb"))
    return result


class PreferGroupByAllRule(FormatterRule):
    """Format and lint: rewrite explicit GROUP BY col list to GROUP BY ALL when equivalent."""

    def __init__(self, severity: str = "warn", overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-group-by-all"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        """Rewrite GROUP BY <cols> → GROUP BY ALL when all non-agg SELECT cols are covered."""
        for select in tree.find_all(exp.Select):
            if not self.enabled_for_node(select):
                continue
            group = select.args.get("group")
            if not group or not group.expressions:
                continue
            if group.args.get("all"):
                continue

            non_agg = _non_agg_sqls(select)
            if not non_agg:
                continue

            group_sqls = {e.sql(dialect="duckdb") for e in group.expressions}
            if non_agg == group_sqls:
                group.set("all", True)
                group.set("expressions", [])

        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for select in tree.find_all(exp.Select):
            if not self.enabled_for_node(select):
                continue
            group = select.args.get("group")
            if not group or not group.expressions:
                continue
            if group.args.get("all"):
                # Already GROUP BY ALL — nothing to flag
                continue

            non_agg = _non_agg_sqls(select)
            if not non_agg:
                continue

            group_sqls = {e.sql(dialect="duckdb") for e in group.expressions}
            if non_agg == group_sqls:
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
