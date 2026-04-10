"""Tests for DuckDB-specific lint rules."""

from __future__ import annotations

from jarify.config import JarifyConfig
from jarify.linter import lint_sql


def _lint(sql: str, **config_overrides) -> list[str]:
    config = JarifyConfig(**config_overrides)
    return [v.rule for v in lint_sql(sql, config)]


class TestDuckdbTypeStyle:
    def test_warns_on_float(self):
        # FLOAT survives DuckDB parsing as DType.FLOAT (not normalized to REAL)
        rules = _lint("CREATE TABLE t (a FLOAT)")
        assert "duckdb-type-style" in rules

    def test_warns_on_varchar(self):
        # NVARCHAR survives as DType.NVARCHAR (VARCHAR is normalized to TEXT at parse time)
        rules = _lint("CREATE TABLE t (a NVARCHAR)")
        assert "duckdb-type-style" in rules

    def test_no_warn_on_canonical_int(self):
        rules = _lint("CREATE TABLE t (a INT)")
        assert "duckdb-type-style" not in rules

    def test_no_warn_on_text(self):
        rules = _lint("CREATE TABLE t (a TEXT)")
        assert "duckdb-type-style" not in rules

    def test_off_disables(self):
        rules = _lint("CREATE TABLE t (a FLOAT)", duckdb_type_style="off")
        assert "duckdb-type-style" not in rules


class TestDuckdbPreferQualify:
    def test_warns_on_subquery_window_filter(self):
        sql = """
        SELECT *
        FROM (
            SELECT a, ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) AS rn
            FROM t
        ) AS sub
        WHERE rn = 1
        """
        rules = _lint(sql)
        assert "duckdb-prefer-qualify" in rules

    def test_no_warn_when_qualify_used(self):
        sql = "SELECT a, ROW_NUMBER() OVER (PARTITION BY b ORDER BY c) AS rn FROM t QUALIFY rn = 1"
        rules = _lint(sql)
        assert "duckdb-prefer-qualify" not in rules

    def test_no_warn_on_plain_subquery(self):
        sql = "SELECT * FROM (SELECT a, b FROM t WHERE a > 1) AS sub WHERE b > 2"
        rules = _lint(sql)
        assert "duckdb-prefer-qualify" not in rules

    def test_off_disables(self):
        sql = "SELECT * FROM (SELECT a, ROW_NUMBER() OVER () AS rn FROM t) sub WHERE rn = 1"
        rules = _lint(sql, duckdb_prefer_qualify="off")
        assert "duckdb-prefer-qualify" not in rules
