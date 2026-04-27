"""Configuration loading and rule definitions for jarify."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAME = "jarify.toml"


@dataclass
class JarifyConfig:
    """Top-level configuration for the jarify formatter/linter."""

    # --- dialect & output ---
    dialect: str = "duckdb"
    indent: int = 2
    max_line_length: int = 120

    # --- keyword / identifier casing ---
    uppercase_keywords: bool = True

    # --- comma style ---
    trailing_commas: bool = False
    leading_commas: bool = True  # team style: leading commas

    # --- formatting rules ---
    normalize_join: bool = True  # bare JOIN → INNER JOIN
    require_alias_as: bool = True  # always require AS keyword for aliases
    one_column_per_line: bool = True  # each SELECT column on its own line
    prefer_from_first: bool = True  # SELECT * FROM t → FROM t (DuckDB FROM-first syntax)

    # --- general lint rules (severity: "off" | "warn" | "error") ---
    no_select_star: str = "warn"
    no_implicit_cross_join: str = "warn"
    no_unused_cte: str = "warn"

    # --- DuckDB-specific lint rules ---
    duckdb_type_style: str = "warn"  # prefer canonical DuckDB type names
    duckdb_prefer_qualify: str = "warn"  # prefer QUALIFY over subquery window filter
    cte_naming: str = "warn"  # CTE names must start with an underscore
    prefer_group_by_all: str = "warn"  # suggest GROUP BY ALL when listing all non-agg cols
    prefer_using_over_on: str = "warn"  # suggest USING (col) over ON a.col = b.col
    consistent_empty_array: str = "warn"  # prefer [] over '[]'::type[] empty array
    no_select_star_in_cte: str = "warn"  # flag SELECT * inside CTE bodies
    prefer_neq_operator: str = "warn"  # rewrite <> to != inequality operator
    prefer_if_over_case: str = "warn"  # rewrite single-WHEN CASE to IF()

    # --- per-rule overrides (populated from [rules.*] in toml) ---
    rules: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # leading_commas and trailing_commas are mutually exclusive;
        # leading_commas takes precedence if explicitly set
        if self.leading_commas:
            self.trailing_commas = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JarifyConfig:
        rules = data.pop("rules", {})
        # Flatten any per-rule severity shortcuts from [rules.no_select_star] etc.
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered, rules=rules)


def find_config(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for a jarify.toml config file."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / DEFAULT_CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Path | None = None, start: Path | None = None) -> JarifyConfig:
    """Load config from a file path, or discover one automatically.

    *start* seeds the upward search when no explicit *path* is given.
    Pass the parent directory of the file being processed (e.g. from
    ``--stdin-filename``) so config discovery anchors to that file rather
    than ``cwd``.
    """
    config_path = path or find_config(start)
    if config_path is None:
        return JarifyConfig()
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return JarifyConfig.from_dict(data.get("jarify", data))
