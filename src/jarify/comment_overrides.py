"""Parse comment-based rule overrides for linting and formatting."""

from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from typing import Any

from jarify.config import JarifyConfig

RULE_ALIASES: dict[str, str] = {
    "keyword-case": "keyword-case",
    "trailing-commas": "trailing-commas",
    "no-implicit-cross-join": "no-implicit-cross-join",
    "no-select-star": "no-select-star",
    "no-unused-cte": "no-unused-cte",
    "duckdb-type-style": "duckdb-type-style",
    "duckdb-prefer-qualify": "duckdb-prefer-qualify",
    "cte-naming": "cte-naming",
    "prefer-group-by-all": "prefer-group-by-all",
    "prefer-using-over-on": "prefer-using-over-on",
    "consistent-empty-array": "consistent-empty-array",
    "no-select-star-in-cte": "no-select-star-in-cte",
    "prefer-neq-operator": "prefer-neq-operator",
    "prefer-if-over-case": "prefer-if-over-case",
    "prefer-ifnull-over-coalesce": "prefer-ifnull-over-coalesce",
    "parse-error": "parse-error",
    "all": "all",
}

SETTING_ALIASES: dict[str, str] = {
    "max-line-length": "max_line_length",
    "line-length": "max_line_length",
    "max_line_length": "max_line_length",
}

_DIRECTIVE_RE = re.compile(r"jarify:\s*(.+)", re.IGNORECASE)
_RANGE_END = 10**9


@dataclasses.dataclass(frozen=True)
class _RuleRange:
    start: int
    end: int
    rule: str


@dataclasses.dataclass(frozen=True)
class _SettingRange:
    start: int
    end: int
    name: str
    value: Any


@dataclasses.dataclass(frozen=True)
class CommentOverrides:
    """Comment-driven overrides resolved to line-aware lookups."""

    file_disabled_rules: frozenset[str] = frozenset()
    line_disabled_rules: dict[int, frozenset[str]] = dataclasses.field(default_factory=dict)
    rule_ranges: tuple[_RuleRange, ...] = ()
    setting_ranges: tuple[_SettingRange, ...] = ()

    def is_rule_disabled(self, rule: str, line: int | None) -> bool:
        normalized = normalize_rule_name(rule)
        if normalized in self.file_disabled_rules or "all" in self.file_disabled_rules:
            return True
        if line is None:
            return False
        line_rules = self.line_disabled_rules.get(line, frozenset())
        if normalized in line_rules or "all" in line_rules:
            return True
        return any(rng.rule in {normalized, "all"} and rng.start <= line <= rng.end for rng in self.rule_ranges)

    def config_for_line(self, config: JarifyConfig, line: int | None) -> JarifyConfig:
        if line is None:
            return config
        updates: dict[str, Any] = {}
        for rng in self.setting_ranges:
            if rng.start <= line <= rng.end:
                updates[rng.name] = rng.value
        return dataclasses.replace(config, **updates) if updates else config


@dataclasses.dataclass
class _ParsedDirective:
    kind: str
    args: str


def normalize_rule_name(name: str) -> str:
    normalized = name.strip().lower().replace("_", "-")
    return RULE_ALIASES.get(normalized, normalized)


def normalize_setting_name(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_")
    return SETTING_ALIASES.get(normalized, normalized)


def _stmt_end_line(lines: list[str], after_line_no: int) -> int:
    """Return the 1-indexed line number of the end of the SQL statement that
    starts on or after *after_line_no* (1-indexed).

    Scans forward for the first line that ends with a bare ``;`` (the jarify
    canonical terminator) or for end-of-file.  Block comments and directive
    comments are skipped so a ``;`` inside a comment does not terminate early.
    """
    for i in range(after_line_no, len(lines)):  # 0-indexed
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped == ";" or stripped.endswith(";"):
            return i + 1  # convert to 1-indexed
    return len(lines)


def parse_comment_overrides(sql: str) -> CommentOverrides:
    """Return parsed comment directives from raw SQL text."""

    file_disabled_rules: set[str] = set()
    line_disabled_rules: dict[int, set[str]] = defaultdict(set)
    rule_ranges: list[_RuleRange] = []
    setting_ranges: list[_SettingRange] = []

    open_rule_ranges: dict[str, int] = {}
    open_setting_ranges: dict[str, tuple[int, Any]] = {}

    lines = sql.splitlines()
    for line_no, raw_line in enumerate(lines, start=1):
        directive = _parse_directive(raw_line)
        if directive is None:
            continue

        if directive.kind == "disable-file":
            for rule in _parse_rules(directive.args):
                file_disabled_rules.add(rule)
            continue

        if directive.kind == "disable-line":
            for rule in _parse_rules(directive.args):
                line_disabled_rules[line_no].add(rule)
            continue

        if directive.kind == "disable-next-line":
            stmt_end = _stmt_end_line(lines, line_no)  # line_no is 1-indexed; lines is 0-indexed
            for rule in _parse_rules(directive.args):
                rule_ranges.append(_RuleRange(line_no + 1, stmt_end, rule))
            continue

        if directive.kind == "disable":
            start = line_no + 1
            for rule in _parse_rules(directive.args):
                open_rule_ranges.setdefault(rule, start)
            continue

        if directive.kind == "enable":
            for rule in _parse_rules(directive.args):
                if rule in open_rule_ranges:
                    rule_ranges.append(_RuleRange(open_rule_ranges.pop(rule), line_no - 1, rule))
            continue

        if directive.kind == "set":
            name, value = _parse_setting(directive.args)
            if name is None:
                continue
            open_setting_ranges[name] = (line_no + 1, value)
            continue

        if directive.kind == "reset":
            name = normalize_setting_name(directive.args)
            if name in open_setting_ranges:
                start, value = open_setting_ranges.pop(name)
                setting_ranges.append(_SettingRange(start, line_no - 1, name, value))

    for rule, start in open_rule_ranges.items():
        rule_ranges.append(_RuleRange(start, _RANGE_END, rule))
    for name, (start, value) in open_setting_ranges.items():
        setting_ranges.append(_SettingRange(start, _RANGE_END, name, value))

    frozen_lines = {line: frozenset(rules) for line, rules in line_disabled_rules.items()}
    return CommentOverrides(
        file_disabled_rules=frozenset(file_disabled_rules),
        line_disabled_rules=frozen_lines,
        rule_ranges=tuple(rule_ranges),
        setting_ranges=tuple(setting_ranges),
    )


def _parse_directive(line: str) -> _ParsedDirective | None:
    match = _DIRECTIVE_RE.search(line)
    if not match:
        return None
    body = match.group(1).strip().rstrip("*/ ")
    for kind in ("disable-file", "disable-next-line", "disable-line", "disable", "enable", "set", "reset"):
        if body.lower().startswith(kind):
            return _ParsedDirective(kind=kind, args=body[len(kind) :].strip())
    return None


def _parse_rules(args: str) -> list[str]:
    return [normalize_rule_name(part) for part in re.split(r"[\s,]+", args) if part.strip()]


def _parse_setting(args: str) -> tuple[str | None, Any]:
    if "=" not in args:
        return None, None
    raw_name, raw_value = [part.strip() for part in args.split("=", 1)]
    name = normalize_setting_name(raw_name)
    if name == "max_line_length":
        return name, int(raw_value)
    return name, raw_value
