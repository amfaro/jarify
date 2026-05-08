"""Configuration loading and rule definitions for jarify."""

from __future__ import annotations

import copy
import os
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAME = "jarify.toml"
GLOBAL_CONFIG_NAMES = ("config.toml", DEFAULT_CONFIG_NAME)


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
    explicit_cross_join_needs_condition: str = "warn"
    cross_join_with_where_condition: str = "error"
    no_unused_cte: str = "warn"

    # --- DuckDB-specific lint rules ---
    duckdb_type_style: str = "warn"  # prefer canonical DuckDB type names
    duckdb_prefer_qualify: str = "warn"  # prefer QUALIFY over subquery window filter
    cte_naming: str = "warn"  # CTE names must start with an underscore
    prefer_group_by_all: str = "warn"  # suggest GROUP BY ALL when listing all non-agg cols
    prefer_using_over_on: str = "warn"  # suggest USING (col) over ON a.col = b.col
    consistent_empty_array: str = "warn"  # prefer [] over '[]'::type[] empty array
    prefer_neq_operator: str = "warn"  # rewrite <> to != inequality operator
    prefer_if_over_case: str = "warn"  # rewrite single-WHEN CASE to IF()
    prefer_ifnull_over_coalesce: str = "warn"  # rewrite two-argument COALESCE(x, y) to ifnull(x, y)

    # --- per-rule overrides (populated from [rules.*] in toml) ---
    rules: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # leading_commas and trailing_commas are mutually exclusive;
        # leading_commas takes precedence if explicitly set
        if self.leading_commas:
            self.trailing_commas = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JarifyConfig:
        config_data = dict(data)
        rules = config_data.pop("rules", {})
        # Flatten any per-rule severity shortcuts from [rules.no_select_star] etc.
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k.replace("-", "_"): v for k, v in config_data.items() if k.replace("-", "_") in known_fields}
        return cls(**filtered, rules=rules)


def find_config(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for a jarify.toml config file."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / DEFAULT_CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def iter_global_config_paths() -> Iterator[Path]:
    """Yield global config candidates in precedence order."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_jarify_dir = Path(xdg_config_home).expanduser() / "jarify"
        for name in GLOBAL_CONFIG_NAMES:
            yield xdg_jarify_dir / name

    default_jarify_dir = Path.home() / ".config" / "jarify"
    for name in GLOBAL_CONFIG_NAMES:
        yield default_jarify_dir / name

    yield Path.home() / DEFAULT_CONFIG_NAME


def find_global_config() -> Path | None:
    """Return the first existing user-global config file, if any."""
    for candidate in iter_global_config_paths():
        if candidate.is_file():
            return candidate
    return None


def _load_config_data(path: Path) -> dict[str, Any]:
    """Load raw config data from *path*."""
    with path.open("rb") as f:
        data = tomllib.load(f)
    return copy.deepcopy(data.get("jarify", data))


def _merge_config_data(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge config data, with *overlay* values taking precedence."""
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _merge_config_data(base_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(path: Path | None = None, start: Path | None = None) -> JarifyConfig:
    """Load config from a file path, or discover one automatically.

    *start* seeds the upward search when no explicit *path* is given.
    Pass the parent directory of the file being processed (e.g. from
    ``--stdin-filename``) so config discovery anchors to that file rather
    than ``cwd``. Discovered project config is overlaid onto the first
    discovered global config.
    """
    if path is not None:
        return JarifyConfig.from_dict(_load_config_data(path))

    project_config_path = find_config(start)
    global_config_path = find_global_config()
    if project_config_path is not None and global_config_path is not None:
        data = _merge_config_data(_load_config_data(global_config_path), _load_config_data(project_config_path))
        return JarifyConfig.from_dict(data)
    if project_config_path is not None:
        return JarifyConfig.from_dict(_load_config_data(project_config_path))
    if global_config_path is not None:
        return JarifyConfig.from_dict(_load_config_data(global_config_path))
    return JarifyConfig()
