"""Built-in formatting and linting rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarify.rules.base import FormatterRule
from jarify.rules.consistent_empty_array import ConsistentEmptyArrayRule
from jarify.rules.cte_naming import CteNamingRule
from jarify.rules.duckdb_prefer_qualify import DuckdbPreferQualifyRule
from jarify.rules.duckdb_type_style import DuckdbTypeStyleRule
from jarify.rules.keyword_case import KeywordCaseRule
from jarify.rules.no_implicit_cross_join import NoImplicitCrossJoinRule
from jarify.rules.no_select_star import NoSelectStarRule
from jarify.rules.no_select_star_in_cte import NoSelectStarInCteRule
from jarify.rules.no_unused_cte import NoUnusedCteRule
from jarify.rules.prefer_group_by_all import PreferGroupByAllRule
from jarify.rules.prefer_if_over_case import PreferIfOverCaseRule
from jarify.rules.prefer_neq_operator import PreferNeqOperatorRule
from jarify.rules.prefer_using_over_on import PreferUsingOverOnRule
from jarify.rules.trailing_commas import TrailingCommasRule

if TYPE_CHECKING:
    from jarify.comment_overrides import CommentOverrides
    from jarify.config import JarifyConfig


def get_default_rules(config: JarifyConfig, overrides: CommentOverrides | None = None) -> list[FormatterRule]:
    """Return the full rule set based on the given config.

    Rules are ordered: format-transforming rules run before lint-only rules.
    """
    rules: list[FormatterRule] = []

    # --- Formatting rules (AST transformers) ---
    if config.uppercase_keywords:
        rules.append(KeywordCaseRule(uppercase=True, overrides=overrides))
    if config.trailing_commas and not config.leading_commas:
        rules.append(TrailingCommasRule(overrides=overrides))
    if config.no_implicit_cross_join != "off":
        rules.append(NoImplicitCrossJoinRule(severity=config.no_implicit_cross_join, overrides=overrides))

    # --- General lint rules (checkers, no AST mutation) ---
    if config.no_select_star != "off":
        rules.append(
            NoSelectStarRule(
                severity=config.no_select_star,
                prefer_from_first=config.prefer_from_first,
                overrides=overrides,
            )
        )
    if config.no_unused_cte != "off":
        rules.append(NoUnusedCteRule(severity=config.no_unused_cte, overrides=overrides))

    # --- DuckDB-specific lint rules ---
    if config.duckdb_type_style != "off":
        rules.append(DuckdbTypeStyleRule(severity=config.duckdb_type_style, overrides=overrides))
    if config.duckdb_prefer_qualify != "off":
        rules.append(DuckdbPreferQualifyRule(severity=config.duckdb_prefer_qualify, overrides=overrides))
    if config.cte_naming != "off":
        rules.append(CteNamingRule(severity=config.cte_naming, overrides=overrides))
    if config.prefer_group_by_all != "off":
        rules.append(PreferGroupByAllRule(severity=config.prefer_group_by_all, overrides=overrides))
    if config.prefer_using_over_on != "off":
        rules.append(PreferUsingOverOnRule(severity=config.prefer_using_over_on, overrides=overrides))
    if config.consistent_empty_array != "off":
        rules.append(ConsistentEmptyArrayRule(severity=config.consistent_empty_array, overrides=overrides))
    if config.no_select_star_in_cte != "off":
        rules.append(NoSelectStarInCteRule(severity=config.no_select_star_in_cte, overrides=overrides))
    if config.prefer_neq_operator != "off":
        rules.append(PreferNeqOperatorRule(severity=config.prefer_neq_operator, overrides=overrides))
    if config.prefer_if_over_case != "off":
        rules.append(PreferIfOverCaseRule(severity=config.prefer_if_over_case, overrides=overrides))

    return rules
