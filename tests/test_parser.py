"""Tests for the SQL parser module."""

import io
import sys

import pytest

from jarify.parser import _quote_reserved_cast_types, parse_sql, parse_sql_lenient


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


def test_parse_lenient_emits_nothing_to_stderr():
    """ErrorLevel.WARN side-effect must not bleed through to the caller's stderr."""
    captured = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured
    try:
        parse_sql_lenient("THIS IS NOT VALID SQL @@@!!!")
    finally:
        sys.stderr = old_stderr
    assert captured.getvalue() == "", f"Unexpected stderr output: {captured.getvalue()!r}"


class TestReservedKeywordTypeCasts:
    """::reserved_keyword[] cast type names must parse and round-trip correctly."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT []::filter[]",
            "SELECT COALESCE(x, []::filter[])",
            "SELECT array_transform(COALESCE(x, []::filter[]), f -> f.a)",
            "SELECT CASE WHEN 1=1 THEN []::filter[] END",
            "SELECT x::filter",
        ],
    )
    def test_reserved_type_name_parses(self, sql: str) -> None:
        """Queries using reserved keywords as type names must not raise."""
        trees = parse_sql(sql)
        assert len(trees) == 1
        assert trees[0] is not None

    def test_non_reserved_type_name_unchanged(self) -> None:
        """Non-reserved type names must not be altered by the pre-processor."""
        sql = "SELECT []::my_struct[], x::text, y::int"
        assert _quote_reserved_cast_types(sql) == sql

    def test_reserved_type_name_quoted(self) -> None:
        assert _quote_reserved_cast_types("SELECT []::filter[]") == 'SELECT []::"filter"[]'

    def test_reserved_type_name_no_array_suffix_quoted(self) -> None:
        assert _quote_reserved_cast_types("SELECT x::filter") == 'SELECT x::"filter"'

    def test_filter_inside_case_parses(self) -> None:
        """The exact pattern from real-world DuckDB macros must parse cleanly."""
        sql = """
        SELECT CASE x
          WHEN 'a' THEN (
             y
            ,array_transform(
               COALESCE(z, []::filter[]),
               f -> (f.a, f.b)::s
             )
          )::mystruct::json
        END
        """
        trees = parse_sql(sql)
        assert len(trees) == 1
        assert trees[0] is not None

    def test_already_quoted_left_unchanged(self) -> None:
        """Already-quoted type names must not be double-quoted."""
        sql = 'SELECT []::"filter"[]'
        result = _quote_reserved_cast_types(sql)
        assert '""' not in result
