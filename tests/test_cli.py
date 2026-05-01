"""Tests for CLI behavior."""

from pathlib import Path

from click.testing import CliRunner

from jarify.cli import main


def test_fmt_stdin_always_writes_sql_to_stdout_when_unchanged() -> None:
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
