"""Tests for CLI behavior."""

from pathlib import Path

from click.testing import CliRunner

from jarify.cli import main


def test_rules_cmd_text_output() -> None:
    """'jarify rules' lists all rules with headers."""
    result = CliRunner().invoke(main, ["rules"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "RULE" in result.output
    assert "no-select-star" in result.output
    assert "prefer-if-over-case" in result.output


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
