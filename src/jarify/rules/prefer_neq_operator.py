"""Rule: rewrite <> to != in inequality expressions."""

from __future__ import annotations

import sqlglot.expressions as exp

from jarify.rules.base import FormatterRule, _node_pos
from jarify.types import LintViolation


class PreferNeqOperatorRule(FormatterRule):
    """Prefer != over <> for inequality comparisons.

    Both operators are equivalent in DuckDB, but != is the modern standard.

    **Format**: The JarifyGenerator's ``neq_sql`` override always emits ``!=``,
    so ``apply()`` is a no-op here — the rewrite happens at generation time.

    **Lint**: Because sqlglot normalises both ``!=`` and ``<>`` to the same
    ``exp.NEQ`` AST node, the lint check cannot distinguish the two from the
    AST alone.  The check flags every ``NEQ`` node so that users running
    ``jarify lint`` without first formatting are told to prefer ``!=``.
    False positives (SQL already using ``!=``) are harmless: running
    ``jarify fmt`` confirms the canonical form and silences the flag.
    """

    def __init__(self, severity: str = "warn") -> None:
        self.severity = severity

    @property
    def name(self) -> str:
        return "prefer-neq-operator"

    def apply(self, tree: exp.Expression) -> exp.Expression:
        # The JarifyGenerator.neq_sql override handles the rewrite to `!=`.
        return tree

    def check(self, tree: exp.Expression) -> list[LintViolation]:
        if self.severity == "off":
            return []
        violations: list[LintViolation] = []
        for node in tree.find_all(exp.NEQ):
            _line, _col = _node_pos(node)
            violations.append(
                LintViolation(
                    rule=self.name,
                    severity=self.severity,
                    message="Prefer != over <> for inequality comparisons",
                    line=_line,
                    column=_col,
                )
            )
        return violations
