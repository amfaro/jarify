"""Shared data types used across the jarify package.

Keeping these here breaks the circular dependency between
jarify.linter (which imports from jarify.rules) and the rule
modules (which need LintViolation).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LintViolation:
    """A single linting violation produced by a rule's check() method."""

    rule: str
    message: str
    severity: str = "warn"  # "warn" | "error"
    line: int | None = None
    column: int | None = None

    def __str__(self) -> str:
        loc = ""
        if self.line is not None:
            loc = f":{self.line}"
            if self.column is not None:
                loc += f":{self.column}"
        return f"[{self.severity.upper()}][{self.rule}]{loc} {self.message}"
