"""Core formatter: parse SQL, apply rules, and regenerate formatted output."""

from __future__ import annotations

from sqlglot.expressions import Expression

from jarify.config import JarifyConfig
from jarify.generator import JarifyGenerator
from jarify.parser import parse_sql
from jarify.rules import get_default_rules
from jarify.rules.base import FormatterRule


def format_sql(sql: str, config: JarifyConfig | None = None) -> str:
    """Format a SQL string according to the configured rules."""
    config = config or JarifyConfig()
    trees = parse_sql(sql, dialect=config.dialect)
    rules = get_default_rules(config)
    generator = JarifyGenerator(config)
    formatted_parts: list[str] = []

    for tree in trees:
        if tree is None:
            continue
        tree = _apply_rules(tree, rules)
        formatted_parts.append(generator.generate(tree))

    return ";\n\n".join(formatted_parts) + (";\n" if formatted_parts else "")


def _apply_rules(tree: Expression, rules: list[FormatterRule]) -> Expression:
    """Walk the tree and apply each formatting rule."""
    for rule in rules:
        tree = rule.apply(tree)
    return tree
