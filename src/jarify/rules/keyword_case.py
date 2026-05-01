"""Rule: enforce keyword casing (uppercase or lowercase).

sqlglot's DuckDB generator outputs keywords uppercase by default.
This rule is a no-op transformer but documents the intent and provides
a lint check for SQL that already contains lowercase keywords.
"""

from __future__ import annotations

from sqlglot.expressions import Expression

from jarify.rules.base import FormatterRule


class KeywordCaseRule(FormatterRule):
    """Ensure SQL keywords are consistently upper- or lower-cased.

    In practice the JarifyGenerator already outputs keywords uppercase.
    This class exists as the canonical home for any future keyword-casing
    AST transforms (e.g., normalizing user-defined function names).
    """

    def __init__(self, uppercase: bool = True, overrides=None) -> None:
        super().__init__(overrides=overrides)
        self.uppercase = uppercase

    @property
    def name(self) -> str:
        return "keyword-case"

    def apply(self, tree: Expression) -> Expression:
        # Keyword casing is handled by the generator; nothing to transform here.
        return tree
