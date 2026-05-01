"""Core linter: parse SQL and report style violations without modifying the source."""

from __future__ import annotations

from jarify.comment_overrides import parse_comment_overrides
from jarify.config import JarifyConfig
from jarify.parser import _mask_ifnull, _mask_numeric, _mask_rust_fmt_placeholders, parse_sql_lenient
from jarify.rules import get_default_rules
from jarify.sqlmesh import looks_like_sqlmesh, mask_sqlmesh_runtime_tokens, split_sqlmesh_segments
from jarify.types import LintViolation

__all__ = ["LintViolation", "lint_sql"]


def lint_sql(sql: str, config: JarifyConfig | None = None) -> list[LintViolation]:
    """Lint a SQL string and return a list of violations."""
    config = config or JarifyConfig()
    if not looks_like_sqlmesh(sql):
        return _lint_sql_core(sql, config)

    violations: list[LintViolation] = []
    for segment in split_sqlmesh_segments(sql):
        if segment.kind == "sql" and segment.text.strip():
            violations.extend(_lint_sql_core(segment.text, config))
    return violations


def _lint_sql_core(sql: str, config: JarifyConfig) -> list[LintViolation]:
    """Lint one SQL segment."""
    overrides = parse_comment_overrides(sql)
    masked_sql, _ = _mask_rust_fmt_placeholders(sql)
    masked_sql, _ = mask_sqlmesh_runtime_tokens(masked_sql)
    masked_sql = _mask_ifnull(masked_sql)
    masked_sql = _mask_numeric(masked_sql)
    trees, parse_errors = parse_sql_lenient(masked_sql, dialect=config.dialect)
    violations: list[LintViolation] = []

    for err in parse_errors:
        if not overrides.is_rule_disabled("parse-error", None):
            violations.append(LintViolation(rule="parse-error", message=str(err), severity="error"))

    rules = get_default_rules(config, overrides=overrides)
    for tree in trees:
        if tree is None:
            continue
        for rule in rules:
            violations.extend(rule.check(tree))

    return violations
