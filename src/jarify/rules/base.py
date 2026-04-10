"""Base class for formatter/linter rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlglot.expressions import Expression

    from jarify.types import LintViolation


class FormatterRule(ABC):
    """A rule that can both check (lint) and transform (format) a SQL AST."""

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
