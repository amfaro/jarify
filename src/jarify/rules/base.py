"""Base class for formatter/linter rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlglot.expressions import Expression

    from jarify.comment_overrides import CommentOverrides
    from jarify.types import LintViolation


def _node_pos(node: Expression) -> tuple[int | None, int | None]:
    """Return (line, col) for a sqlglot node.

    sqlglot stores position in ``node.meta`` for leaf-level nodes (Identifiers,
    Literals, etc.). Higher-level nodes (CTE, Join, Select, …) often have an
    empty ``meta``, so we fall back to the first descendant that carries a
    position.
    """
    line = node.meta.get("line")
    col = node.meta.get("col")
    if line is not None:
        return line, col
    for child in node.walk():
        line = child.meta.get("line")
        col = child.meta.get("col")
        if line is not None:
            return line, col
    return None, None


class FormatterRule(ABC):
    """A rule that can both check (lint) and transform (format) a SQL AST."""

    def __init__(self, overrides: CommentOverrides | None = None) -> None:
        self._overrides = overrides

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this rule, e.g. 'keyword-case'."""

    @abstractmethod
    def apply(self, tree: Expression) -> Expression:
        """Transform the tree in-place and return it."""

    def check(self, tree: Expression) -> list[LintViolation]:
        """Return violations found in the tree. Default: no violations."""
        return []

    def enabled_for_line(self, line: int | None) -> bool:
        return not (self._overrides and self._overrides.is_rule_disabled(self.name, line))

    def enabled_for_node(self, node: Expression) -> bool:
        line, _ = _node_pos(node)
        return self.enabled_for_line(line)


class LintOnlyRule(FormatterRule):
    """Base class for rules that only check (lint) and never transform the AST."""

    def apply(self, tree: Expression) -> Expression:
        return tree
