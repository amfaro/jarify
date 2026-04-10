"""Rule: flag '[]'::type[] string-cast empty arrays; prefer [] literal."""

from __future__ import annotations

import sqlglot.expressions as exp
from sqlglot.expressions import DataType

from jarify.rules.base import FormatterRule
from jarify.types import LintViolation


class ConsistentEmptyArrayRule(FormatterRule):
    """Lint: flag '[]'::type[] (string-cast) in favour of native [] empty array literal."""

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "consistent-empty-array"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []

        for cast in tree.find_all(exp.Cast):
            if not (isinstance(cast.to, exp.DataType) and cast.to.this == DataType.Type.ARRAY):
                continue

            canonical = cast.to.sql(dialect="duckdb")

            # Pattern 1: '[]'::type[] — literal directly cast to array
            if isinstance(cast.this, exp.Literal) and cast.this.is_string and cast.this.name == "[]":
                violations.append(
                    LintViolation(
                        rule=self.name,
                        severity=self.severity,
                        message=(
                            f"Use the native empty array literal [] instead of '[]'::{canonical};"
                            " cast the COALESCE result to the target type when needed"
                        ),
                    )
                )

            # Pattern 2: COALESCE(x, '[]')::type[] — '[]' string fallback inside COALESCE
            elif isinstance(cast.this, exp.Coalesce):
                for arg in cast.this.expressions:
                    if isinstance(arg, exp.Literal) and arg.is_string and arg.name == "[]":
                        violations.append(
                            LintViolation(
                                rule=self.name,
                                severity=self.severity,
                                message=(
                                    f"Use [] instead of '[]' as the COALESCE fallback in COALESCE(...)::{ canonical};"
                                    " prefer native empty array literal"
                                ),
                            )
                        )
                        break

        return violations
