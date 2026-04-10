"""Tests for the SQL formatter."""

from jarify.config import JarifyConfig
from jarify.formatter import format_sql


def test_format_simple_select():
    result, _ = format_sql("select 1")
    assert result.strip() != ""


def test_format_preserves_semantics():
    sql = "SELECT a, b FROM my_table WHERE x > 1"
    result, _ = format_sql(sql)
    # The formatted output should still be valid SQL containing the same elements
    assert "a" in result
    assert "b" in result
    assert "my_table" in result


def test_format_multiple_statements():
    sql = "SELECT 1; SELECT 2"
    result, _ = format_sql(sql)
    assert result.count(";") == 2


def test_format_respects_config():
    config = JarifyConfig(indent=4)
    result, _ = format_sql("SELECT a FROM b WHERE c = 1", config)
    assert result.strip() != ""


def test_semicolon_on_own_line():
    result, _ = format_sql("SELECT a FROM t")
    lines = result.splitlines()
    assert lines[-1].strip() == ";", f"Expected last line to be ';', got: {lines[-1]!r}"


def test_semicolon_own_line_multi_statement():
    sql = "SELECT 1; SELECT 2"
    result, _ = format_sql(sql)
    for line in result.splitlines():
        # No line should end with a semicolon — semicolons always on their own line
        stripped = line.rstrip()
        if stripped:
            assert not stripped.endswith(";") or stripped == ";", (
                f"Semicolon at end of non-blank line: {stripped!r}"
            )


def test_as_alignment():
    sql = "SELECT first_name AS first, last_name AS last, email AS email_address FROM t"
    result, _ = format_sql(sql)
    lines = [line for line in result.splitlines() if " AS " in line]
    as_positions = [line.index(" AS ") for line in lines]
    assert len(set(as_positions)) == 1, f"AS keywords not aligned: {as_positions}"


def test_parse_failure_returns_original_with_warning():
    """Unparseable SQL is returned unchanged with a warning instead of crashing."""
    bad_sql = "THIS IS NOT VALID SQL @@@!!!"
    result, warnings = format_sql(bad_sql)
    assert result == bad_sql
    assert len(warnings) == 1
    assert "could not parse" in str(warnings[0])
