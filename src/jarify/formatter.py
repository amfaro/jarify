"""Core formatter: parse SQL, apply rules, and regenerate formatted output."""

from __future__ import annotations

import re

from sqlglot.errors import ParseError
from sqlglot.expressions import Expression
from sqlglot.tokens import Tokenizer as SqlglotTokenizer

from jarify.comment_overrides import parse_comment_overrides
from jarify.config import JarifyConfig
from jarify.generator import JarifyGenerator
from jarify.parser import (
    _extract_ctas_body_placeholders,
    _extract_line_rust_fmt_placeholders,
    _mask_ifnull,
    _mask_numeric,
    _mask_rust_fmt_placeholders,
    _reinsert_line_rust_fmt_placeholders,
    _restore_ctas_body_placeholders,
    _unmask_ifnull,
    _unmask_numeric,
    _unmask_rust_fmt_placeholders,
    parse_sql,
)
from jarify.rules import get_default_rules
from jarify.rules.base import FormatterRule, _node_pos
from jarify.sqlmesh import (
    looks_like_sqlmesh,
    mask_sqlmesh_runtime_tokens,
    split_sqlmesh_segments,
    unmask_sqlmesh_runtime_tokens,
)


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
    if not looks_like_sqlmesh(sql):
        return _format_sql_core(sql, config)

    warnings: list[FormatWarning] = []
    formatted_segments: list[str] = []
    for segment in split_sqlmesh_segments(sql):
        if segment.kind == "opaque" or not segment.text.strip():
            formatted_segments.append(segment.text)
            continue
        formatted, segment_warnings = _format_sql_core(segment.text, config)
        formatted_segments.append(formatted)
        warnings.extend(segment_warnings)

    return "".join(formatted_segments), warnings


def _format_sql_core(sql: str, config: JarifyConfig) -> tuple[str, list[FormatWarning]]:
    """Format a parseable SQL segment, preserving existing non-SQLMesh behavior."""
    warnings: list[FormatWarning] = []
    overrides = parse_comment_overrides(sql)

    # Pre-process: replace whole-line placeholders used as CTAS bodies (those
    # following a line that ends with AS) with a dummy SELECT so sqlglot
    # receives a complete, parseable CTAS and does not silently drop the AS.
    processed_sql, ctas_body_map = _extract_ctas_body_placeholders(sql)

    # Strip whole-line Rust format placeholders so sqlglot never sees them.
    # They are re-inserted verbatim after formatting using the recorded anchors.
    # Inline placeholders are masked with dummy identifiers that survive the AST.
    stripped_sql, line_insertions = _extract_line_rust_fmt_placeholders(processed_sql)
    masked_sql, inline_mask = _mask_rust_fmt_placeholders(stripped_sql)
    masked_sql, sqlmesh_mask = mask_sqlmesh_runtime_tokens(masked_sql)
    masked_sql = _mask_ifnull(masked_sql)
    masked_sql = _mask_numeric(masked_sql)

    try:
        trees = parse_sql(masked_sql, dialect=config.dialect)
    except ParseError as exc:
        result = _try_pivot_order_by_workaround(masked_sql, config)
        if result is not None:
            result = _unmask_numeric(result)
            result = _unmask_ifnull(result)
            result = unmask_sqlmesh_runtime_tokens(result, sqlmesh_mask)
            result = _unmask_rust_fmt_placeholders(result, inline_mask)
            result = _reinsert_line_rust_fmt_placeholders(result, line_insertions)
            return _restore_ctas_body_placeholders(result, ctas_body_map), warnings
        warnings.append(FormatWarning(f"could not parse SQL (formatting skipped): {exc}"))
        return sql, warnings

    rules = get_default_rules(config, overrides=overrides)
    leading_comment_texts = _find_leading_comment_texts(masked_sql)
    trailing_sep_comment_texts = _find_trailing_sep_comment_texts(masked_sql)
    formatted_parts: list[str] = []

    for tree in trees:
        if tree is None:
            continue
        tree = _apply_rules(tree, rules)
        tree_line, _ = _node_pos(tree)
        tree_config = overrides.config_for_line(config, tree_line)
        generator = JarifyGenerator(tree_config)
        generator._leading_comment_texts = leading_comment_texts
        generator._trailing_sep_comment_texts = trailing_sep_comment_texts
        formatted_parts.append(generator.generate(tree))

    # Join statements but hold off on the trailing ;\n -- it must come *after*
    # no-anchor line placeholders are re-inserted, otherwise a trailing
    # {placeholder} ends up after the semicolon instead of before it, which
    # breaks SQL templates that use the placeholder as an optional WHERE clause.
    # A trailing \n is appended to ensure the last line ends with a newline so
    # that no-anchor placeholder re-insertion does not concatenate directly onto
    # the last SQL token without a line break.
    formatted = "\n;\n\n".join(formatted_parts) + ("\n" if formatted_parts else "")
    formatted = _unmask_numeric(formatted)
    formatted = _unmask_ifnull(formatted)
    formatted = unmask_sqlmesh_runtime_tokens(formatted, sqlmesh_mask)
    formatted = _unmask_rust_fmt_placeholders(formatted, inline_mask)
    result = _reinsert_line_rust_fmt_placeholders(formatted, line_insertions)
    if formatted_parts:
        result = result.rstrip() + "\n;\n"
    return _restore_ctas_body_placeholders(result, ctas_body_map), warnings


# ---------------------------------------------------------------------------
# Leading-comment detection
# ---------------------------------------------------------------------------


def _find_leading_comment_texts(sql: str) -> frozenset[str]:
    """Return stripped texts of comments that appear on their own line before a token.

    A comment is "leading" when it occupies the region between the previous
    token's end and the current token's start in the source text.  This lets
    the generator distinguish ``-- note\nfoo`` (leading) from ``foo -- note``
    (trailing) even though sqlglot stores both in the same ``node.comments``
    list.

    See also :func:`_find_trailing_sep_comment_texts` for comments that appear
    on their own line *after* an expression but before its following comma
    separator (e.g. between two SELECT columns).
    """
    from sqlglot.tokens import TokenType

    tokens = SqlglotTokenizer().tokenize(sql)
    leading: set[str] = set()
    for idx, tok in enumerate(tokens):
        if not tok.comments:
            continue
        prev_end = tokens[idx - 1].end if idx > 0 else 0
        before = sql[prev_end : tok.start]
        prev_type = tokens[idx - 1].token_type if idx > 0 else None
        for comment in tok.comments:
            stripped = comment.strip()
            if not stripped or f"-- {stripped}" not in before:
                continue
            # When the owning token is a comma AND the preceding token is a
            # plain expression (not a closing paren), sqlglot's parser moves
            # the comment to the *preceding* expression node.  That makes it
            # trailing-sep, not leading.  Skip it here; captured by
            # _find_trailing_sep_comment_texts instead.
            if tok.token_type == TokenType.COMMA and prev_type != TokenType.R_PAREN:
                continue
            leading.add(stripped)
    return frozenset(leading)


def _find_trailing_sep_comment_texts(sql: str) -> frozenset[str]:
    """Return stripped texts of comments that sit on their own line *after* an
    expression and *before* the comma separator that follows it.

    Example::

        ,qualifier
         -- this comment lives between qualifier and str_split_regex
        ,str_split_regex(...)

    sqlglot attaches such a comment to the preceding expression (``qualifier``)
    because the comma token that follows the comment owns it at tokenise-time
    and the parser moves it backwards.  The generator must render these after
    the expression's line so they stay between the two columns.
    """
    from sqlglot.tokens import TokenType

    tokens = SqlglotTokenizer().tokenize(sql)
    trailing_sep: set[str] = set()
    for idx, tok in enumerate(tokens):
        if not tok.comments or tok.token_type != TokenType.COMMA:
            continue
        prev_type = tokens[idx - 1].token_type if idx > 0 else None
        # Closing paren before comma = end of a body/subquery; the comment
        # belongs to the *next* expression (e.g. a CTE name), not this rule.
        if prev_type == TokenType.R_PAREN:
            continue
        prev_end = tokens[idx - 1].end if idx > 0 else 0
        before = sql[prev_end : tok.start]
        for comment in tok.comments:
            stripped = comment.strip()
            if stripped and f"-- {stripped}" in before:
                trailing_sep.add(stripped)
    return frozenset(trailing_sep)


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
