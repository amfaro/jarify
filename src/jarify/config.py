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
FUNCTION_CASE_FIELDS = ("uppercase_functions", "lowercase_functions")


class ConfigError(ValueError):
    """Raised when a jarify configuration is invalid."""


@dataclass
class JarifyConfig:
    """Top-level configuration for the jarify formatter/linter."""

    # --- dialect & output ---
    dialect: str = "duckdb"
    indent: int = 2
    max_line_length: int = 120
    min_column_alias: int | None = None
    alias_visual_guide_interval: int | None = None

    # --- keyword / identifier casing ---
    uppercase_keywords: bool = True
    # Function names (case-insensitive) whose case overrides the built-in
    # aggregate/window → UPPER, everything else → lower classification.
    uppercase_functions: list[str] = field(default_factory=list)
    lowercase_functions: list[str] = field(default_factory=list)

    # --- comma style ---
    trailing_commas: bool = False
    leading_commas: bool = True  # team style: leading commas

    # --- formatting rules ---
    normalize_join: bool = True  # bare JOIN → INNER JOIN
    explicit_outer_join: bool = False  # LEFT/RIGHT JOIN → LEFT/RIGHT OUTER JOIN (default drops OUTER)
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

        # Non-positive alias columns and guide intervals are treated as unset.
        if self.min_column_alias is not None and self.min_column_alias <= 0:
            self.min_column_alias = None
        if self.alias_visual_guide_interval is not None and self.alias_visual_guide_interval <= 0:
            self.alias_visual_guide_interval = None

        for name in FUNCTION_CASE_FIELDS:
            value = getattr(self, name)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ConfigError(f"{name} must be a list of function names, got {value!r}")
        both = {f.lower() for f in self.uppercase_functions} & {f.lower() for f in self.lowercase_functions}
        if both:
            raise ConfigError(
                "function names cannot be in both uppercase_functions and lowercase_functions: "
                + ", ".join(sorted(both))
            )

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
    """Load raw config data from *path*.

    Raises ``ConfigError`` naming *path* if its function case lists are invalid,
    so an error is attributed to the right file before global and project
    config are merged.
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    data = copy.deepcopy(data.get("jarify", data))
    try:
        JarifyConfig.from_dict({k: v for k, v in data.items() if k.replace("-", "_") in FUNCTION_CASE_FIELDS})
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from None
    return data


def _merge_config_data(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge config data, with *overlay* values taking precedence.

    Tables merge key by key; any other value, including a list such as
    ``uppercase_functions``, replaces the base value as a whole.
    """
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _merge_config_data(base_value, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _function_case_names(data: dict[str, Any], name: str) -> set[str]:
    """Return the lowercased names in a function case list of raw config *data*."""
    names: set[str] = set()
    for key in (name, name.replace("_", "-")):
        value = data.get(key)
        if isinstance(value, list):
            names.update(item.lower() for item in value if isinstance(item, str))
    return names


def _drop_function_case_overrides(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Remove from *base* the function names *overlay* lists with the opposite case.

    A project that lists ``list`` in ``lowercase_functions`` thereby overrides a
    global ``uppercase_functions = ["list"]`` instead of the merged config
    listing the name in both lists.
    """
    base = copy.deepcopy(base)
    upper, lower = (_function_case_names(overlay, name) for name in FUNCTION_CASE_FIELDS)
    for name, overridden in zip(FUNCTION_CASE_FIELDS, (lower, upper), strict=True):
        for key in (name, name.replace("_", "-")):
            value = base.get(key)
            if isinstance(value, list):
                base[key] = [item for item in value if not (isinstance(item, str) and item.lower() in overridden)]
    return base


def load_config(path: Path | None = None, start: Path | None = None) -> JarifyConfig:
    """Load config from a file path, or discover one automatically.

    *start* seeds the upward search when no explicit *path* is given.
    Pass the parent directory of the file being processed (e.g. from
    ``--stdin-filename``) so config discovery anchors to that file rather
    than ``cwd``. Discovered project config is overlaid onto the first
    discovered global config.

    Raises ``ConfigError`` when a config file is invalid.
    """
    if path is not None:
        return JarifyConfig.from_dict(_load_config_data(path))

    project_config_path = find_config(start)
    global_config_path = find_global_config()
    if project_config_path is not None and global_config_path is not None:
        global_data = _load_config_data(global_config_path)
        project_data = _load_config_data(project_config_path)
        data = _merge_config_data(_drop_function_case_overrides(global_data, project_data), project_data)
        return JarifyConfig.from_dict(data)
    if project_config_path is not None:
        return JarifyConfig.from_dict(_load_config_data(project_config_path))
    if global_config_path is not None:
        return JarifyConfig.from_dict(_load_config_data(global_config_path))
    return JarifyConfig()
