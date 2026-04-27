"""Rule: rewrite explicit GROUP BY column list to GROUP BY ALL when equivalent."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation

# DuckDB's list() aggregate is parsed by sqlglot as exp.List (Func, not AggFunc).
# Treat it the same as AggFunc so it does not count as a free column reference.
_AGG_TYPES = (exp.AggFunc, exp.List)


def _free_col_refs(expr: exp.Expression) -> set[str]:
    """Return SQL strings of Column nodes in *expr* that are not inside any AggFunc.

    For a purely non-aggregate expression like ``LOWER(name)`` this returns
    ``{"name"}`` (the leaf column, not the whole expression).  Callers that
    need the full expression SQL for purely non-aggregate items should call
    ``expr.sql()`` directly instead.
    """
    if isinstance(expr, _AGG_TYPES):
        return set()
    if isinstance(expr, exp.Column):
        return {expr.sql(dialect="duckdb")}
    result: set[str] = set()
    for child in expr.args.values():
        if isinstance(child, list):
            for c in child:
                if isinstance(c, exp.Expression):
                    result |= _free_col_refs(c)
        elif isinstance(child, exp.Expression):
            result |= _free_col_refs(child)
    return result


def _non_agg_sqls(select: exp.Select) -> set[str]:
    """Derive the set of "non-aggregate expressions" that GROUP BY ALL would use.

    Rules:
    - If a SELECT item contains **no** AggFunc anywhere, the whole item counts
      as a GROUP BY candidate (e.g. ``LOWER(name)``, ``col1``).
    - If a SELECT item is a **mixed** expression (contains an AggFunc *and*
      free column references outside that AggFunc), those free column refs are
      the GROUP BY candidates (e.g. ``'prefix' || col1 || STRING_AGG(x)``
      contributes ``col1``).
    - Pure aggregate items (e.g. ``SUM(col)`` with no outer column refs)
      contribute nothing.
    """
    result: set[str] = set()
    for item in select.expressions:
        inner = item.this if isinstance(item, exp.Alias) else item
        if not inner.find(*_AGG_TYPES):
            # Entirely non-aggregate — use the whole expression as-is.
            result.add(inner.sql(dialect="duckdb"))
        else:
            # Mixed or pure aggregate — collect free (non-agg) column refs.
            result |= _free_col_refs(inner)
    return result


class PreferGroupByAllRule(FormatterRule):
    """Format and lint: rewrite explicit GROUP BY col list to GROUP BY ALL when equivalent."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-group-by-all"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        """Rewrite GROUP BY <cols> → GROUP BY ALL when all non-agg SELECT cols are covered."""
        for select in tree.find_all(exp.Select):
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
