"""Tests for the SQL parser module."""

import io
import sys

import pytest

from jarify.parser import (
    _extract_ctas_body_placeholders,
    _extract_line_rust_fmt_placeholders,
    _mask_rust_fmt_placeholders,
    _quote_reserved_cast_types,
    _reinsert_line_rust_fmt_placeholders,
    _restore_ctas_body_placeholders,
    _unmask_rust_fmt_placeholders,
    parse_sql,
    parse_sql_lenient,
)


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

    def test_transform_macro_parses_as_anonymous_function(self) -> None:
        sql = "SELECT transform(t, _transform)"
        trees = parse_sql(sql)
        assert len(trees) == 1
        tree = trees[0]
        assert tree is not None
        assert tree.sql(dialect="duckdb") == "SELECT TRANSFORM(t, _transform)"

    def test_already_quoted_left_unchanged(self) -> None:
        """Already-quoted type names must not be double-quoted."""
        sql = 'SELECT []::"filter"[]'
        result = _quote_reserved_cast_types(sql)
        assert '""' not in result


class TestRustFmtPlaceholderMasking:
    """_mask/_unmask_rust_fmt_placeholders must round-trip cleanly."""

    def test_single_placeholder_masked(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        masked, mapping = _mask_rust_fmt_placeholders(sql)
        assert "{where_clause}" not in masked
        assert len(mapping) == 1
        assert "{where_clause}" in mapping.values()

    def test_multiple_placeholders_get_unique_markers(self) -> None:
        sql = "FROM {table_name}\n{where_clause}\n;"
        _masked, mapping = _mask_rust_fmt_placeholders(sql)
        assert len(mapping) == 2
        assert len(set(mapping.keys())) == 2

    def test_unmask_restores_original(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        masked, mapping = _mask_rust_fmt_placeholders(sql)
        restored = _unmask_rust_fmt_placeholders(masked, mapping)
        assert restored == sql

    def test_no_placeholders_returns_empty_mapping(self) -> None:
        sql = "SELECT a FROM t WHERE x = 1"
        masked, mapping = _mask_rust_fmt_placeholders(sql)
        assert masked == sql
        assert mapping == {}

    def test_duckdb_struct_literal_not_masked(self) -> None:
        # {key: value} struct syntax must not be treated as a Rust placeholder
        sql = "SELECT {name: 'alice', age: 30}"
        masked, mapping = _mask_rust_fmt_placeholders(sql)
        assert masked == sql
        assert mapping == {}

    def test_line_level_placeholder_uses_comment_marker(self) -> None:
        # Whole-line placeholder → block comment so it is valid between clauses
        sql = "FROM examples\n{where_clause}\n;"
        _masked, mapping = _mask_rust_fmt_placeholders(sql)
        marker = next(iter(mapping))
        assert marker.startswith("/*") and marker.endswith("*/")

    def test_inline_placeholder_uses_identifier_marker(self) -> None:
        # Inline placeholder → dummy identifier so it is valid as a name/expression
        sql = "FROM {table_name} WHERE x = 1"
        _masked, mapping = _mask_rust_fmt_placeholders(sql)
        marker = next(iter(mapping))
        assert not marker.startswith("/*")

    def test_masked_sql_parses_without_error(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        masked, _ = _mask_rust_fmt_placeholders(sql)
        trees = parse_sql(masked)
        assert len(trees) == 1
        assert trees[0] is not None

    def test_inline_masked_sql_parses_without_error(self) -> None:
        sql = "FROM {table_name} WHERE x = 1"
        masked, _ = _mask_rust_fmt_placeholders(sql)
        trees = parse_sql(masked)
        assert len(trees) == 1
        assert trees[0] is not None


class TestExtractReinsertLinePlaceholders:
    """Strip/reinsert helpers used by the formatter must preserve placeholder lines."""

    def test_strip_removes_placeholder_line(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        assert "{where_clause}" not in stripped
        assert len(insertions) == 1
        assert insertions[0][0] == ["{where_clause}"]

    def test_anchor_is_next_non_blank_line(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        _, insertions = _extract_line_rust_fmt_placeholders(sql)
        assert insertions[0][2] == ";"

    def test_reinsert_restores_before_anchor(self) -> None:
        sql = "FROM examples\n{where_clause}\n;"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        # Simulate a trivial "format" that just strips trailing whitespace
        formatted = stripped.rstrip() + "\n"
        result = _reinsert_line_rust_fmt_placeholders(formatted, insertions)
        assert "{where_clause}" in result
        lines = result.splitlines()
        placeholder_idx = lines.index("{where_clause}")
        semicolon_idx = lines.index(";")
        assert placeholder_idx < semicolon_idx

    def test_round_trip_preserves_sql(self) -> None:
        sql = "FROM examples\n{where_clause}\n;\n"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        restored = _reinsert_line_rust_fmt_placeholders(stripped, insertions)
        assert restored == sql

    def test_round_trip_preserves_indented_placeholder(self) -> None:
        sql = "(\n  FROM programs\n    {where_clause}\n)\n;\n"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        assert "{where_clause}" not in stripped
        assert insertions[0][0] == ["    {where_clause}"]
        restored = _reinsert_line_rust_fmt_placeholders(stripped, insertions)
        assert restored == sql

    def test_no_placeholders_returns_unchanged(self) -> None:
        sql = "SELECT a FROM t WHERE x = 1\n;\n"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        assert stripped == sql
        assert insertions == []

    def test_consecutive_placeholders_form_one_group(self) -> None:
        sql = "{program_filter}\n{example_filter}\n\nCREATE TABLE t AS SELECT 1\n;\n"
        _, insertions = _extract_line_rust_fmt_placeholders(sql)
        # Consecutive placeholders collapse into a single group with a shared
        # SQL anchor so they are re-inserted together in their original order.
        assert len(insertions) == 1
        assert insertions[0] == (
            ["{program_filter}", "{example_filter}"],
            ["\n"],
            "CREATE TABLE t AS SELECT 1",
            None,  # no prev_anchor — nothing before the group
        )

    def test_blank_lines_after_placeholder_block_are_preserved(self) -> None:
        sql = "{program_filter}\n{example_filter}\n\nCREATE TABLE t AS SELECT 1\n;\n"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        # The blank line between the placeholder block and the SQL must be
        # consumed during extraction so the formatter does not see it as
        # leading whitespace (and strip it).
        assert not stripped.startswith("\n"), "blank line must not leak into stripped SQL"
        # After reinsertion the blank line must be restored.
        restored = _reinsert_line_rust_fmt_placeholders(stripped, insertions)
        assert restored == sql

    def test_consecutive_placeholders_reinserted_in_order(self) -> None:
        sql = "{program_filter}\n{example_filter}\n\nCREATE TABLE t AS SELECT 1\n;\n"
        stripped, insertions = _extract_line_rust_fmt_placeholders(sql)
        restored = _reinsert_line_rust_fmt_placeholders(stripped, insertions)
        lines = restored.splitlines()
        prog_idx = lines.index("{program_filter}")
        ex_idx = lines.index("{example_filter}")
        create_idx = next(i for i, ln in enumerate(lines) if ln.startswith("CREATE TABLE"))
        assert prog_idx < ex_idx < create_idx

    def test_prev_anchor_disambiguates_duplicate_anchor_text(self) -> None:
        """Regression: placeholder with anchor ')' must land in the correct CTE.

        When two CTEs both close with a bare ')' line, the reinsert algorithm
        must use prev_anchor to place the placeholder after the right preceding
        line instead of always taking the first occurrence.
        """
        sql = (
            "WITH a AS (\n"
            "  SELECT *\n"
            "  FROM sku_catalog\n"
            ")\n"
            ",b AS (\n"
            "  SELECT count(*) AS n\n"
            "  FROM _final f\n"
            "  {manufacturer_filter}\n"
            ")\n"
            "SELECT n FROM b\n;"
        )
        from jarify.formatter import format_sql

        result, warnings = format_sql(sql)
        lines = result.splitlines()
        # The placeholder must appear inside CTE b (after "FROM _final f"),
        # not inside CTE a (after "FROM sku_catalog").
        mf_idx = lines.index("  {manufacturer_filter}")
        # Find the line index for "FROM _final f" and "FROM sku_catalog"
        final_f_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "FROM _final f")
        sku_catalog_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "FROM sku_catalog")
        assert mf_idx > final_f_idx, "placeholder must come after 'FROM _final f'"
        assert mf_idx > sku_catalog_idx, "placeholder must not be in the sku_catalog CTE"
        assert warnings == []


class TestCtasBodyPlaceholders:
    """_extract/_restore_ctas_body_placeholders must handle CTAS body placeholders."""

    def test_ctas_body_placeholder_detected(self) -> None:
        sql = "CREATE OR REPLACE TABLE {t} AS\n{query_body}\n"
        modified, ctas_body_map = _extract_ctas_body_placeholders(sql)
        assert len(ctas_body_map) == 1
        assert "{query_body}" in ctas_body_map.values()
        assert "{query_body}" not in modified
        assert "SELECT * FROM" in modified

    def test_non_ctas_placeholder_not_affected(self) -> None:
        sql = "FROM examples\n{where_clause}\n;\n"
        modified, ctas_body_map = _extract_ctas_body_placeholders(sql)
        assert ctas_body_map == {}
        assert modified == sql

    def test_inline_placeholder_not_affected(self) -> None:
        sql = "SELECT * FROM {table_name}\n;\n"
        modified, ctas_body_map = _extract_ctas_body_placeholders(sql)
        assert ctas_body_map == {}
        assert modified == sql

    def test_restore_replaces_marker_line(self) -> None:
        sql = "CREATE OR REPLACE TABLE {t} AS\n{query_body}\n"
        _modified, ctas_body_map = _extract_ctas_body_placeholders(sql)
        # Simulate a formatted line containing the marker
        marker = next(iter(ctas_body_map))
        formatted = f"CREATE OR REPLACE TABLE t AS\nFROM {marker}\n;\n"
        restored = _restore_ctas_body_placeholders(formatted, ctas_body_map)
        assert marker not in restored
        assert "{query_body}" in restored
        assert "FROM" not in restored

    def test_restore_no_op_when_map_empty(self) -> None:
        sql = "SELECT 1\n;\n"
        assert _restore_ctas_body_placeholders(sql, {}) == sql

    def test_multiple_ctas_bodies_get_unique_markers(self) -> None:
        sql = "CREATE TABLE {t1} AS\n{body1}\n;\n\nCREATE TABLE {t2} AS\n{body2}\n"
        _modified, ctas_body_map = _extract_ctas_body_placeholders(sql)
        assert len(ctas_body_map) == 2
        assert len(set(ctas_body_map.keys())) == 2
        assert "{body1}" in ctas_body_map.values()
        assert "{body2}" in ctas_body_map.values()
