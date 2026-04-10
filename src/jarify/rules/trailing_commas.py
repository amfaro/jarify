"""Rule: enforce trailing commas in SELECT lists.

The actual comma placement is controlled by the JarifyGenerator
(via its `leading_comma` constructor parameter). This rule is kept
as the canonical owner of lint-checking for mixed comma styles.
"""

from __future__ import annotations

from sqlglot.expressions import Expression

from jarify.rules.base import FormatterRule


class TrailingCommasRule(FormatterRule):
    """Ensure SELECT column lists use trailing (not leading) commas.

    Comma placement is enforced by the JarifyGenerator at output time.
    This class exists as the canonical registration point and can grow
    lint checks in future iterations.
    """

    @property
    def name(self) -> str:
        return "trailing-commas"

    def apply(self, tree: Expression) -> Expression:
        # Handled by JarifyGenerator(leading_comma=False).
        return tree
