"""Built-in formatting and linting rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from jarify.rules.base import FormatterRule
from jarify.rules.consistent_empty_array import ConsistentEmptyArrayRule
from jarify.rules.cte_naming import CteNamingRule
from jarify.rules.duckdb_prefer_qualify import DuckdbPreferQualifyRule
from jarify.rules.duckdb_type_style import DuckdbTypeStyleRule
from jarify.rules.keyword_case import KeywordCaseRule
from jarify.rules.no_implicit_cross_join import NoImplicitCrossJoinRule
from jarify.rules.no_select_star import NoSelectStarRule
from jarify.rules.no_unused_cte import NoUnusedCteRule
from jarify.rules.prefer_group_by_all import PreferGroupByAllRule
from jarify.rules.prefer_if_over_case import PreferIfOverCaseRule
from jarify.rules.prefer_ifnull_over_coalesce import PreferIfnullOverCoalesceRule
from jarify.rules.prefer_neq_operator import PreferNeqOperatorRule
from jarify.rules.prefer_using_over_on import PreferUsingOverOnRule
from jarify.rules.trailing_commas import TrailingCommasRule

if TYPE_CHECKING:
    from jarify.comment_overrides import CommentOverrides
    from jarify.config import JarifyConfig


@dataclass(frozen=True)
class RuleInfo:
    """Static metadata for a single jarify rule."""

    name: str
    """Kebab-case rule identifier used in violation output and disable directives."""
    config_key: str
    """Snake_case key in ``jarify.toml`` that controls this rule."""
    default: str
    """Default value: ``"on"`` for always-on formatting rules, or a severity string."""
    auto_fix: bool
    """True when ``jarify fmt`` automatically rewrites violations."""
    description: str
    """One-line description of what the rule does."""


#: Complete catalog of all built-in jarify rules in display order.
RULE_CATALOG: list[RuleInfo] = [
    RuleInfo(
        name="keyword-case",
        config_key="uppercase_keywords",
        default="on",
        auto_fix=True,
        description="uppercase SQL keywords; lowercase type and scalar function names",
    ),
    RuleInfo(
        name="trailing-commas",
        config_key="trailing_commas",
        default="off",
        auto_fix=True,
        description="trailing comma placement (default: leading commas)",
    ),
    RuleInfo(
        name="no-implicit-cross-join",
        config_key="no_implicit_cross_join",
        default="warn",
        auto_fix=True,
        description="rewrite implicit cross joins to explicit CROSS JOIN",
    ),
    RuleInfo(
        name="no-select-star",
        config_key="no_select_star",
        default="warn",
        auto_fix=False,
        description="flag SELECT * usage, including inside CTE bodies",
    ),
    RuleInfo(
        name="no-unused-cte",
        config_key="no_unused_cte",
        default="warn",
        auto_fix=False,
        description="flag CTEs that are defined but never referenced",
    ),
    RuleInfo(
        name="duckdb-type-style",
        config_key="duckdb_type_style",
        default="warn",
        auto_fix=False,
        description="prefer canonical DuckDB type names (e.g. int not integer)",
    ),
    RuleInfo(
        name="duckdb-prefer-qualify",
        config_key="duckdb_prefer_qualify",
        default="warn",
        auto_fix=False,
        description="prefer QUALIFY clause over subquery window filter",
    ),
    RuleInfo(
        name="cte-naming",
        config_key="cte_naming",
        default="warn",
        auto_fix=True,
        description="CTE names must start with an underscore; fmt adds the prefix",
    ),
    RuleInfo(
        name="prefer-group-by-all",
        config_key="prefer_group_by_all",
        default="warn",
        auto_fix=True,
        description="rewrite explicit GROUP BY column list to GROUP BY ALL",
    ),
    RuleInfo(
        name="prefer-using-over-on",
        config_key="prefer_using_over_on",
        default="warn",
        auto_fix=False,
        description="suggest USING (col) over ON a.col = b.col for equality joins",
    ),
    RuleInfo(
        name="consistent-empty-array",
        config_key="consistent_empty_array",
        default="warn",
        auto_fix=True,
        description="rewrite '[]'::type[] cast form to bare [] empty array literal",
    ),
    RuleInfo(
        name="prefer-neq-operator",
        config_key="prefer_neq_operator",
        default="warn",
        auto_fix=True,
        description="rewrite <> inequality operator to !=",
    ),
    RuleInfo(
        name="prefer-if-over-case",
        config_key="prefer_if_over_case",
        default="warn",
        auto_fix=True,
        description="rewrite single-WHEN CASE expressions to IF()",
    ),
    RuleInfo(
        name="prefer-ifnull-over-coalesce",
        config_key="prefer_ifnull_over_coalesce",
        default="warn",
        auto_fix=True,
        description="rewrite two-argument COALESCE(x, y) to ifnull(x, y)",
    ),
]


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
    if config.prefer_neq_operator != "off":
        rules.append(PreferNeqOperatorRule(severity=config.prefer_neq_operator, overrides=overrides))
    if config.prefer_if_over_case != "off":
        rules.append(PreferIfOverCaseRule(severity=config.prefer_if_over_case, overrides=overrides))
    if config.prefer_ifnull_over_coalesce != "off":
        rules.append(
            PreferIfnullOverCoalesceRule(
                severity=config.prefer_ifnull_over_coalesce,
                overrides=overrides,
            )
        )

    return rules
