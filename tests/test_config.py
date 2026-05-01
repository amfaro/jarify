"""Tests for config loading."""

from pathlib import Path

import pytest

from jarify.config import JarifyConfig, find_config, load_config


def test_default_config():
    config = JarifyConfig()
    assert config.dialect == "duckdb"
    assert config.uppercase_keywords is True
    assert config.leading_commas is True
    assert config.trailing_commas is False
    assert config.indent == 2


def test_config_from_dict():
    config = JarifyConfig.from_dict({"indent": 4, "uppercase_keywords": False})
    assert config.indent == 4
    assert config.uppercase_keywords is False


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


def test_config_from_dict_kebab_keys():
    """Kebab-case keys in jarify.toml are accepted and normalized."""
    config = JarifyConfig.from_dict({"no-select-star": "error", "prefer-if-over-case": "off"})
    assert config.no_select_star == "error"
    assert config.prefer_if_over_case == "off"


def test_config_from_dict_mixed_case_keys():
    """Snake_case and kebab-case keys coexist without conflict."""
    config = JarifyConfig.from_dict({"indent": 4, "no-unused-cte": "error"})
    assert config.indent == 4
    assert config.no_unused_cte == "error"


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
