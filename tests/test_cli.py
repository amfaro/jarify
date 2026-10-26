"""Tests for CLI behavior."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from jarify.cli import main


def test_rules_cmd_text_output() -> None:
    """'jarify rules' lists all rules with headers."""
    result = CliRunner().invoke(main, ["rules"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "RULE" in result.output
    assert "no-select-star" in result.output
    assert "prefer-if-over-case" in result.output
    assert "prefer-ifnull-over-coalesce" in result.output


def test_rules_cmd_json_output() -> None:
    """'jarify rules --format json' emits a valid JSON list of rule objects."""
    import json as _json

    result = CliRunner().invoke(main, ["rules", "--format", "json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = _json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) > 0
    names = {r["name"] for r in data}
    assert "no-select-star" in names
    assert "prefer-if-over-case" in names
    assert "prefer-ifnull-over-coalesce" in names
    # Every entry has the required keys
    required = {"name", "config_key", "default", "auto_fix", "description"}
    for row in data:
        assert required <= row.keys()

    sql = "SELECT\n   1\n;\n"

    result = CliRunner().invoke(main, ["fmt", "-"], input=sql, catch_exceptions=False)

    assert result.exit_code == 0
    assert result.output == sql


def test_fmt_file_reports_unchanged_when_input_is_file(tmp_path: Path) -> None:
    sql_file = tmp_path / "query.sql"
    sql_file.write_text("SELECT\n   1\n;\n")

    result = CliRunner().invoke(main, ["fmt", str(sql_file)], catch_exceptions=False)

    assert result.exit_code == 0
    assert "unchanged" in result.output
    assert str(sql_file) in result.output.replace("\n", "")


def test_show_config_uses_global_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    global_config = home / ".config" / "jarify" / "config.toml"
    global_config.parent.mkdir(parents=True)
    global_config.write_text("[jarify]\nindent = 6\n")

    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["show-config"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "indent" in result.output
    assert "= 6" in result.output
    assert "min_column_alias" not in result.output


def test_show_config_includes_min_column_alias_when_set(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nmin-column-alias = 80\n")

    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["show-config", "--config", str(config_file)], catch_exceptions=False)

    assert result.exit_code == 0
    assert "min_column_alias" in result.output
    assert "= 80" in result.output


def test_init_mentions_min_column_alias(tmp_path: Path) -> None:
    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["init"], catch_exceptions=False)
        starter = Path("jarify.toml").read_text()

    assert result.exit_code == 0
    assert "min_column_alias" in starter


def test_init_mentions_explicit_outer_join(tmp_path: Path) -> None:
    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["init"], catch_exceptions=False)
        starter = Path("jarify.toml").read_text()

    assert result.exit_code == 0
    assert "explicit_outer_join = false" in starter


def test_fmt_explicit_outer_join_from_config(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nexplicit_outer_join = true\n")
    sql = "SELECT a FROM foo LEFT JOIN bar ON foo.id = bar.id"

    result = CliRunner().invoke(main, ["fmt", "--config", str(config_file), "-"], input=sql, catch_exceptions=False)

    assert result.exit_code == 0
    assert "\nLEFT OUTER JOIN bar ON foo.id = bar.id\n" in result.output


def test_show_config_includes_alias_visual_guide_interval_when_set(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nalias-visual-guide-interval = 12\n")

    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["show-config", "--config", str(config_file)], catch_exceptions=False)

    assert result.exit_code == 0
    assert "alias_visual_guide_interval = 12" in result.output


def test_show_config_omits_alias_visual_guide_interval_when_unset(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text("[jarify]\nindent = 2\n")

    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["show-config", "--config", str(config_file)], catch_exceptions=False)

    assert result.exit_code == 0
    assert "alias_visual_guide_interval" not in result.output


def test_init_mentions_alias_visual_guide_interval(tmp_path: Path) -> None:
    with CliRunner().isolated_filesystem(temp_dir=tmp_path):
        result = CliRunner().invoke(main, ["init"], catch_exceptions=False)
        starter = Path("jarify.toml").read_text()

    assert result.exit_code == 0
    assert "alias_visual_guide_interval" in starter


@pytest.mark.parametrize("command", ["fmt", "lint", "show-config"])
def test_function_case_conflict_is_reported_as_config_error(tmp_path: Path, command: str) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text('[jarify]\nuppercase_functions = ["list"]\nlowercase-functions = ["LIST"]\n')
    args = [command, "--config", str(config_file)] + (["-"] if command != "show-config" else [])

    result = CliRunner().invoke(main, args, input="SELECT list(a) FROM t", catch_exceptions=False)

    assert result.exit_code == 2
    output = result.output.replace("\n", "")
    assert "ERROR" in output
    assert "function names cannot be in both uppercase_functions and lowercase_functions: list" in output


def test_fmt_applies_function_case_overrides_from_config(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text('[jarify]\nuppercase-functions = ["list"]\nlowercase_functions = ["any_value"]\n')

    result = CliRunner().invoke(
        main,
        ["fmt", "--config", str(config_file), "-"],
        input="SELECT list(a) AS l, any_value(b) AS v FROM t",
        catch_exceptions=False,
    )

    assert result.output == "SELECT\n   LIST(a)      AS l\n  ,any_value(b) AS v\nFROM t\n;\n"


def test_show_config_prints_function_case_lists_as_toml_arrays(tmp_path: Path) -> None:
    config_file = tmp_path / "jarify.toml"
    config_file.write_text('[jarify]\nuppercase_functions = ["list", "ifnull"]\n')

    result = CliRunner().invoke(main, ["show-config", "--config", str(config_file)], catch_exceptions=False)

    assert result.exit_code == 0
    assert 'uppercase_functions    = ["list", "ifnull"]' in result.output
    assert "lowercase_functions    = []" in result.output
