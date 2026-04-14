"""Rule: warn on non-canonical DuckDB type names."""

from __future__ import annotations

import sqlglot.expressions as exp
from sqlglot.expressions import DataType

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation

# DType variants that survive DuckDB parsing and are non-canonical.
# Maps DType enum value → recommended canonical type name.
_NON_CANONICAL: dict[DataType.Type, str] = {
    DataType.Type.FLOAT: "REAL",
    DataType.Type.VARCHAR: "TEXT",
    DataType.Type.NVARCHAR: "TEXT",
}


class DuckdbTypeStyleRule(FormatterRule):
    """Lint: warn when non-canonical DuckDB type names are used.

    Detectable non-canonical types after DuckDB parsing:
    - FLOAT / FLOAT4  → prefer REAL
    - NVARCHAR        → prefer TEXT

    Note: many aliases (INTEGER→INT, VARCHAR→TEXT, BOOL→BOOLEAN, etc.) are
    fully normalized to canonical forms at parse time by sqlglot and cannot
    be detected here.
    """

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "duckdb-type-style"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for dtype in tree.find_all(exp.DataType):
            canonical = _NON_CANONICAL.get(dtype.this)
            if canonical:
                raw = dtype.this.name
                _line, _col = _node_pos(dtype)
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=f"Prefer '{canonical}' over '{raw}' in DuckDB",
                        line=_line,
                        column=_col,
                    )
                )
        return violations
