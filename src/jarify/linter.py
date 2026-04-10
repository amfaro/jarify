"""Core linter: parse SQL and report style violations without modifying the source."""

from __future__ import annotations

from jarify.config import JarifyConfig
from jarify.parser import parse_sql_lenient
from jarify.rules import get_default_rules
from jarify.types import LintViolation

__all__ = ["LintViolation", "lint_sql"]


def lint_sql(sql: str, config: JarifyConfig | None = None) -> list[LintViolation]:
    """Lint a SQL string and return a list of violations."""
    config = config or JarifyConfig()
    trees, parse_errors = parse_sql_lenient(sql, dialect=config.dialect)
    violations: list[LintViolation] = []

    for err in parse_errors:
        violations.append(LintViolation(rule="parse-error", message=str(err), severity="error"))

    rules = get_default_rules(config)
    for tree in trees:
        if tree is None:
            continue
        for rule in rules:
            violations.extend(rule.check(tree))

    return violations
