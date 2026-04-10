"""Tests for the SQL parser module."""

from jarify.parser import parse_sql, parse_sql_lenient


def test_parse_simple_select():
    trees = parse_sql("SELECT 1")
    assert len(trees) == 1
    assert trees[0] is not None


def test_parse_multiple_statements():
    trees = parse_sql("SELECT 1; SELECT 2")
    assert len(trees) == 2


def test_parse_duckdb_specific():
    trees = parse_sql("SELECT * FROM read_parquet('data.parquet')")
    assert len(trees) == 1


def test_parse_lenient_collects_errors():
    _, errors = parse_sql_lenient("SELECT FROM WHERE")
    # Should parse leniently without raising
    assert isinstance(errors, list)
