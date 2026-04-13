"""Core formatter: parse SQL, apply rules, and regenerate formatted output."""

from __future__ import annotations

import re

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

    Returns ``(formatted_sql, warnings)``. On parse failure the formatter
    first attempts the PIVOT+ORDER BY workaround; if that also fails the
    original SQL is returned unchanged with a warning.
    """
    config = config or JarifyConfig()
    warnings: list[FormatWarning] = []

    try:
        trees = parse_sql(sql, dialect=config.dialect)
    except ParseError as exc:
        result = _try_pivot_order_by_workaround(sql, config)
        if result is not None:
            return result, warnings
        warnings.append(
            FormatWarning(f"could not parse SQL (formatting skipped): {exc}")
        )
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


# ---------------------------------------------------------------------------
# PIVOT + ORDER BY workaround
# ---------------------------------------------------------------------------
# sqlglot does not yet parse `PIVOT (...) ON col USING agg ORDER BY ...`.
# We work around this by splitting the trailing top-level ORDER BY off,
# formatting both halves independently, and recombining.


def _try_pivot_order_by_workaround(sql: str, config: JarifyConfig) -> str | None:
    """Return formatted SQL for PIVOT+ORDER BY, or None if not applicable."""
    split = _split_trailing_order_by(sql)
    if split is None:
        return None

    pivot_sql, order_by_text = split

    # The PIVOT-without-ORDER BY should now parse cleanly
    try:
        trees = parse_sql(pivot_sql, dialect=config.dialect)
    except ParseError:
        return None  # not the PIVOT+ORDER BY pattern we know how to handle

    trees = [t for t in trees if t is not None]
    if not trees:
        return None

    rules = get_default_rules(config)
    generator = JarifyGenerator(config)

    # Format every statement; ORDER BY attaches only to the last one (the PIVOT)
    formatted_parts = [generator.generate(_apply_rules(t, rules)) for t in trees]
    formatted_order_by = _format_order_by_clause(order_by_text, config, generator)

    *preceding, last_pivot = formatted_parts
    pivot_with_order = f"{last_pivot.rstrip()}\n{formatted_order_by.lstrip()}"

    all_parts = [*preceding, pivot_with_order]
    return "\n;\n\n".join(all_parts) + "\n;\n"


def _split_trailing_order_by(sql: str) -> tuple[str, str] | None:
    """Split ``sql`` at the last top-level ORDER BY, ignoring those inside parens.

    Returns ``(pre_order_by, order_by_clause)`` or ``None`` if no top-level
    ORDER BY exists.
    """
    depth = 0
    last_pos: int | None = None

    for m in re.finditer(r"(?:\(|\)|ORDER\s+BY)", sql, re.IGNORECASE):
        token = m.group()
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0:
            last_pos = m.start()

    if last_pos is None:
        return None

    return sql[:last_pos].rstrip(), sql[last_pos:]


def _format_order_by_clause(order_by_text: str, config: JarifyConfig, generator: JarifyGenerator) -> str:
    """Format an ORDER BY clause string using the jarify generator."""
    try:
        # Wrap in a dummy SELECT so sqlglot can parse the ORDER BY
        dummy_trees = parse_sql(f"SELECT 1 {order_by_text}", dialect=config.dialect)
        if dummy_trees and dummy_trees[0] is not None:
            order_node = dummy_trees[0].args.get("order")
            if order_node is not None:
                return generator.sql(order_node)
    except ParseError:
        pass
    return order_by_text.strip()


def _apply_rules(tree: Expression, rules: list[FormatterRule]) -> Expression:
    """Walk the tree and apply each formatting rule."""
    for rule in rules:
        tree = rule.apply(tree)
    return tree
