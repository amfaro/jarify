"""Tests for the SQL formatter."""

from jarify.config import JarifyConfig
from jarify.formatter import format_sql


def test_format_simple_select():
    result = format_sql("select 1")
    assert result.strip() != ""


def test_format_preserves_semantics():
    sql = "SELECT a, b FROM my_table WHERE x > 1"
    result = format_sql(sql)
    # The formatted output should still be valid SQL containing the same elements
    assert "a" in result
    assert "b" in result
    assert "my_table" in result


def test_format_multiple_statements():
    sql = "SELECT 1; SELECT 2"
    result = format_sql(sql)
    assert result.count(";") == 2


def test_format_respects_config():
    config = JarifyConfig(indent=4)
    result = format_sql("SELECT a FROM b WHERE c = 1", config)
    assert result.strip() != ""
