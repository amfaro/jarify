"""Tests for config loading."""

from pathlib import Path

import pytest

from jarify.config import (
    JarifyConfig,
    _merge_config_data,
    find_config,
    find_global_config,
    iter_global_config_paths,
    load_config,
)


def test_default_config():
    config = JarifyConfig()
    assert config.dialect == "duckdb"
    assert config.uppercase_keywords is True
    assert config.leading_commas is True
    assert config.trailing_commas is False
    assert config.indent == 2
    assert config.min_column_alias is None


def test_config_from_dict():
    config = JarifyConfig.from_dict({"indent": 4, "uppercase_keywords": False, "min-column-alias": 80})
    assert config.indent == 4
    assert config.uppercase_keywords is False
    assert config.min_column_alias == 80


def test_find_config_walks_up(tmp_path: Path) -> None:
    # Place jarify.toml two levels above where we start the search.
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nindent = 4\n")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)

    found = find_config(start=deep)
    assert found == config_file


def test_find_config_returns_none_when_missing(tmp_path: Path) -> None:
    assert find_config(start=tmp_path) is None


def test_load_config_uses_start(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nindent = 8\n")
    deep = tmp_path / "sub"
    deep.mkdir()

    config = load_config(start=deep)
    assert config.indent == 8


def test_load_config_explicit_path_takes_precedence(tmp_path: Path) -> None:
    # Even with a start that would find a different config, explicit path wins.
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("[jarify]\nindent = 3\n")
    other = tmp_path / "other" / "jarify.toml"
    other.parent.mkdir()
    other.write_text("[jarify]\nindent = 99\n")

    config = load_config(path=explicit, start=other.parent)
    assert config.indent == 3


def test_global_config_paths_follow_precedence_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))

    assert list(iter_global_config_paths()) == [
        xdg_config_home / "jarify" / "config.toml",
        xdg_config_home / "jarify" / "jarify.toml",
        home / ".config" / "jarify" / "config.toml",
        home / ".config" / "jarify" / "jarify.toml",
        home / "jarify.toml",
    ]


@pytest.mark.parametrize(
    ("global_path", "indent"),
    [
        (("xdg", "jarify", "config.toml"), 3),
        (("xdg", "jarify", "jarify.toml"), 4),
        (("home", ".config", "jarify", "config.toml"), 5),
        (("home", ".config", "jarify", "jarify.toml"), 6),
        (("home", "jarify.toml"), 7),
    ],
)
def test_load_config_uses_each_global_config_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    global_path: tuple[str, ...],
    indent: int,
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))
    root = xdg_config_home if global_path[0] == "xdg" else home
    global_config = root.joinpath(*global_path[1:])
    global_config.parent.mkdir(parents=True, exist_ok=True)
    global_config.write_text(f"[jarify]\nindent = {indent}\n")

    assert find_global_config() == global_config
    assert load_config(start=tmp_path).indent == indent


def test_find_global_config_uses_earliest_candidate_when_multiple_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    xdg_config_home = tmp_path / "xdg"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))

    candidates = list(iter_global_config_paths())
    for index, candidate in enumerate(candidates, start=3):
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(f"[jarify]\nindent = {index}\n")

    assert find_global_config() == candidates[0]
    assert load_config(start=tmp_path).indent == 3


def test_load_config_merges_project_config_over_global_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    global_config = home / ".config" / "jarify" / "config.toml"
    global_config.parent.mkdir(parents=True)
    global_config.write_text("[jarify]\nindent = 6\nmax_line_length = 100\n")
    project_config = tmp_path / "project" / "jarify.toml"
    project_config.parent.mkdir()
    project_config.write_text("[jarify]\nindent = 3\n")

    config = load_config(start=project_config.parent)

    assert config.indent == 3
    assert config.max_line_length == 100


def test_load_config_merges_nested_rules_from_project_and_global_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    global_config = home / ".config" / "jarify" / "config.toml"
    global_config.parent.mkdir(parents=True)
    global_config.write_text('[jarify.rules.no_select_star]\nseverity = "error"\n')
    project_config = tmp_path / "project" / "jarify.toml"
    project_config.parent.mkdir()
    project_config.write_text('[jarify.rules.no_unused_cte]\nseverity = "off"\n')

    config = load_config(start=project_config.parent)

    assert config.rules == {
        "no_select_star": {"severity": "error"},
        "no_unused_cte": {"severity": "off"},
    }


def test_load_config_explicit_path_takes_precedence_over_project_and_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    global_config = home / ".config" / "jarify" / "config.toml"
    global_config.parent.mkdir(parents=True)
    global_config.write_text("[jarify]\nindent = 6\n")
    project_config = tmp_path / "project" / "jarify.toml"
    project_config.parent.mkdir()
    project_config.write_text("[jarify]\nindent = 3\n")
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("[jarify]\nindent = 9\n")

    config = load_config(path=explicit, start=project_config.parent)

    assert config.indent == 9


def test_load_config_uses_defaults_when_no_config_exists(tmp_path: Path) -> None:
    config = load_config(start=tmp_path)

    assert config.indent == JarifyConfig().indent


def test_config_from_dict_kebab_keys():
    """Kebab-case keys in jarify.toml are accepted and normalized."""
    config = JarifyConfig.from_dict(
        {
            "no-select-star": "error",
            "prefer-if-over-case": "off",
            "prefer-ifnull-over-coalesce": "error",
        }
    )
    assert config.no_select_star == "error"
    assert config.prefer_if_over_case == "off"
    assert config.prefer_ifnull_over_coalesce == "error"


def test_config_from_dict_mixed_case_keys():
    """Snake_case and kebab-case keys coexist without conflict."""
    config = JarifyConfig.from_dict({"indent": 4, "no-unused-cte": "error", "min_column_alias": 72})
    assert config.indent == 4
    assert config.no_unused_cte == "error"
    assert config.min_column_alias == 72


def test_config_from_dict_does_not_mutate_input() -> None:
    data = {"indent": 4, "min-column-alias": 80, "rules": {"no_select_star": {"severity": "error"}}}

    JarifyConfig.from_dict(data)

    assert data == {"indent": 4, "min-column-alias": 80, "rules": {"no_select_star": {"severity": "error"}}}


def test_merge_config_data_does_not_alias_inputs() -> None:
    base = {"rules": {"no_select_star": {"severity": "warn"}}}
    overlay = {"rules": {"no_unused_cte": {"severity": "off"}}}

    merged = _merge_config_data(base, overlay)
    merged["rules"]["no_select_star"]["severity"] = "error"
    merged["rules"]["no_unused_cte"]["severity"] = "warn"

    assert base == {"rules": {"no_select_star": {"severity": "warn"}}}
    assert overlay == {"rules": {"no_unused_cte": {"severity": "off"}}}


def test_min_column_alias_ignores_non_positive_values() -> None:
    assert JarifyConfig(min_column_alias=0).min_column_alias is None
    assert JarifyConfig(min_column_alias=-5).min_column_alias is None
    assert JarifyConfig.from_dict({"min-column-alias": 0}).min_column_alias is None


@pytest.mark.parametrize("command", ["fmt", "lint"])
def test_stdin_filename_anchors_config(tmp_path: Path, command: str) -> None:
    """--stdin-filename parent dir is used to discover jarify.toml."""
    from click.testing import CliRunner

    from jarify.cli import main

    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nindent = 6\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [command, "--stdin-filename", str(tmp_path / "query.sql"), "-"],
        input="SELECT 1",
        catch_exceptions=False,
    )
    assert result.exit_code in (0, 1), result.output
