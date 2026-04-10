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
from jarify.rules.prefer_using_over_on import PreferUsingOverOnRule
from jarify.rules.trailing_commas import TrailingCommasRule

if TYPE_CHECKING:
    from jarify.config import JarifyConfig


def get_default_rules(config: JarifyConfig) -> list[FormatterRule]:
    """Return the full rule set based on the given config.

    Rules are ordered: format-transforming rules run before lint-only rules.
    """
    rules: list[FormatterRule] = []

    # --- Formatting rules (AST transformers) ---
    if config.uppercase_keywords:
        rules.append(KeywordCaseRule(uppercase=True))
    if config.trailing_commas and not config.leading_commas:
        rules.append(TrailingCommasRule())

    # --- General lint rules (checkers, no AST mutation) ---
    if config.no_select_star != "off":
        rules.append(NoSelectStarRule(severity=config.no_select_star))
    if config.no_implicit_cross_join != "off":
        rules.append(NoImplicitCrossJoinRule(severity=config.no_implicit_cross_join))
    if config.no_unused_cte != "off":
        rules.append(NoUnusedCteRule(severity=config.no_unused_cte))

    # --- DuckDB-specific lint rules ---
    if config.duckdb_type_style != "off":
        rules.append(DuckdbTypeStyleRule(severity=config.duckdb_type_style))
    if config.duckdb_prefer_qualify != "off":
        rules.append(DuckdbPreferQualifyRule(severity=config.duckdb_prefer_qualify))
    if config.cte_naming != "off":
        rules.append(CteNamingRule(severity=config.cte_naming))
    if config.prefer_group_by_all != "off":
        rules.append(PreferGroupByAllRule(severity=config.prefer_group_by_all))
    if config.prefer_using_over_on != "off":
        rules.append(PreferUsingOverOnRule(severity=config.prefer_using_over_on))
    if config.consistent_empty_array != "off":
        rules.append(ConsistentEmptyArrayRule(severity=config.consistent_empty_array))
    if config.no_select_star_in_cte != "off":
        rules.append(NoSelectStarInCteRule(severity=config.no_select_star_in_cte))

    return rules
