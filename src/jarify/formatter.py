"""Core formatter: parse SQL, apply rules, and regenerate formatted output."""

from __future__ import annotations

from sqlglot.errors import ParseError
from sqlglot.expressions import Expression

from jarify.config import JarifyConfig
from jarify.generator import JarifyGenerator
from jarify.parser import parse_sql
from jarify.rules import get_default_rules
from jarify.rules.base import FormatterRule


class FormatWarning:
    """A non-fatal warning produced during formatting."""

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


def format_sql(
    sql: str,
    config: JarifyConfig | None = None,
) -> tuple[str, list[FormatWarning]]:
    """Format a SQL string according to the configured rules.

    Returns ``(formatted_sql, warnings)``. On parse failure the original SQL
    is returned unchanged with a warning — the caller decides what to do.
    """
    config = config or JarifyConfig()
    warnings: list[FormatWarning] = []

    try:
        trees = parse_sql(sql, dialect=config.dialect)
    except ParseError as exc:
        warnings.append(FormatWarning(f"could not parse SQL (formatting skipped): {exc}"))
        return sql, warnings

    rules = get_default_rules(config)
    generator = JarifyGenerator(config)
    formatted_parts: list[str] = []

    for tree in trees:
        if tree is None:
            continue
        tree = _apply_rules(tree, rules)
        formatted_parts.append(generator.generate(tree))

    formatted = "\n;\n\n".join(formatted_parts) + ("\n;\n" if formatted_parts else "")
    return formatted, warnings


def _apply_rules(tree: Expression, rules: list[FormatterRule]) -> Expression:
    """Walk the tree and apply each formatting rule."""
    for rule in rules:
        tree = rule.apply(tree)
    return tree
