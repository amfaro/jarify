"""Tests for lint rules."""

from __future__ import annotations

from jarify.config import JarifyConfig
from jarify.linter import lint_sql


def _lint(sql: str, **config_overrides) -> list[str]:
    """Helper: lint SQL and return list of rule names that fired."""
    config = JarifyConfig(**config_overrides)
    return [v.rule for v in lint_sql(sql, config)]


class TestNoSelectStar:
    def test_warns_on_select_star(self):
        rules = _lint("SELECT * FROM t")
        assert "no-select-star" in rules

    def test_no_warn_on_explicit_columns(self):
        rules = _lint("SELECT a, b FROM t")
        assert "no-select-star" not in rules

    def test_off_disables_rule(self):
        rules = _lint("SELECT * FROM t", no_select_star="off")
        assert "no-select-star" not in rules

    def test_count_star_not_flagged(self):
        rules = _lint("SELECT COUNT(*) FROM t")
        assert "no-select-star" not in rules


class TestNoUnusedCte:
    def test_warns_on_unused_cte(self):
        sql = "WITH unused AS (SELECT 1 AS x) SELECT 2"
        rules = _lint(sql)
        assert "no-unused-cte" in rules

    def test_no_warn_when_cte_used(self):
        sql = "WITH base AS (SELECT 1 AS x) SELECT x FROM base"
        rules = _lint(sql)
        assert "no-unused-cte" not in rules

    def test_off_disables_rule(self):
        sql = "WITH unused AS (SELECT 1) SELECT 2"
        rules = _lint(sql, no_unused_cte="off")
        assert "no-unused-cte" not in rules

    def test_no_cte_no_violation(self):
        rules = _lint("SELECT a FROM t")
        assert "no-unused-cte" not in rules


class TestLintSeverity:
    def test_violation_has_severity(self):
        from jarify.config import JarifyConfig
        from jarify.linter import lint_sql

        config = JarifyConfig(no_select_star="error")
        violations = lint_sql("SELECT * FROM t", config)
        star_violations = [v for v in violations if v.rule == "no-select-star"]
        assert star_violations
        assert star_violations[0].severity == "error"

    def test_violation_str_includes_severity(self):
        from jarify.config import JarifyConfig
        from jarify.linter import lint_sql

        config = JarifyConfig(no_select_star="warn")
        violations = lint_sql("SELECT * FROM t", config)
        star_violations = [v for v in violations if v.rule == "no-select-star"]
        assert star_violations
        assert "WARN" in str(star_violations[0])


class TestCteNaming:
    def test_warns_on_cte_without_underscore(self):
        sql = "WITH people AS (SELECT 1 AS id) SELECT id FROM people"
        rules = _lint(sql)
        assert "cte-naming" in rules

    def test_no_warn_when_cte_starts_with_underscore(self):
        sql = "WITH _people AS (SELECT 1 AS id) SELECT id FROM _people"
        rules = _lint(sql)
        assert "cte-naming" not in rules

    def test_off_disables_rule(self):
        sql = "WITH people AS (SELECT 1) SELECT 1 FROM people"
        rules = _lint(sql, cte_naming="off")
        assert "cte-naming" not in rules

    def test_multiple_ctes_flags_only_bad_ones(self):
        sql = """
        WITH _good AS (SELECT 1 AS x), bad AS (SELECT 2 AS y)
        SELECT x, y FROM _good, bad
        """
        violations = lint_sql(sql)
        names = [v.rule for v in violations]
        assert "cte-naming" in names
        cte_msgs = [v.message for v in violations if v.rule == "cte-naming"]
        assert any("bad" in m for m in cte_msgs)

    def test_autofix_prefixes_cte_name(self):
        from jarify.formatter import format_sql

        sql = "WITH people AS (SELECT 1 AS id) SELECT id FROM people"
        out, _ = format_sql(sql)
        assert "_people" in out
        assert "WITH people" not in out

    def test_autofix_renames_all_references(self):
        from jarify.formatter import format_sql

        sql = "WITH base AS (SELECT 1 AS x) SELECT x FROM base"
        out, _ = format_sql(sql)
        assert "WITH _base" in out
        assert "FROM _base" in out


class TestPreferGroupByAll:
    def test_warns_when_all_non_agg_cols_listed(self):
        sql = "SELECT a, b, count(*) AS n FROM t GROUP BY a, b"
        rules = _lint(sql)
        assert "prefer-group-by-all" in rules

    def test_no_warn_for_group_by_all(self):
        sql = "SELECT a, b, count(*) AS n FROM t GROUP BY ALL"
        rules = _lint(sql)
        assert "prefer-group-by-all" not in rules

    def test_no_warn_when_group_by_is_subset(self):
        # Only grouping by one of two non-agg columns — not equivalent to GROUP BY ALL
        sql = "SELECT a, b, count(*) AS n FROM t GROUP BY a"
        rules = _lint(sql)
        assert "prefer-group-by-all" not in rules

    def test_off_disables_rule(self):
        sql = "SELECT a, b, count(*) AS n FROM t GROUP BY a, b"
        rules = _lint(sql, prefer_group_by_all="off")
        assert "prefer-group-by-all" not in rules


class TestPreferUsingOverOn:
    def test_warns_on_same_column_name_equijoin(self):
        sql = "SELECT a.x FROM a INNER JOIN b ON a.id = b.id"
        rules = _lint(sql)
        assert "prefer-using-over-on" in rules

    def test_no_warn_when_using_already_used(self):
        sql = "SELECT a.x FROM a INNER JOIN b USING (id)"
        rules = _lint(sql)
        assert "prefer-using-over-on" not in rules

    def test_no_warn_when_columns_differ(self):
        sql = "SELECT a.x FROM a INNER JOIN b ON a.foo = b.bar"
        rules = _lint(sql)
        assert "prefer-using-over-on" not in rules

    def test_off_disables_rule(self):
        sql = "SELECT a.x FROM a INNER JOIN b ON a.id = b.id"
        rules = _lint(sql, prefer_using_over_on="off")
        assert "prefer-using-over-on" not in rules


class TestConsistentEmptyArray:
    def test_warns_on_string_cast_empty_array(self):
        sql = "SELECT COALESCE(tags, '[]')::text[] AS tags FROM t"
        rules = _lint(sql)
        assert "consistent-empty-array" in rules

    def test_no_warn_on_native_empty_array(self):
        sql = "SELECT COALESCE(tags, []) AS tags FROM t"
        rules = _lint(sql)
        assert "consistent-empty-array" not in rules

    def test_off_disables_rule(self):
        sql = "SELECT COALESCE(tags, '[]')::text[] AS tags FROM t"
        rules = _lint(sql, consistent_empty_array="off")
        assert "consistent-empty-array" not in rules


class TestNoSelectStarInCte:
    def test_warns_on_select_star_in_cte(self):
        sql = "WITH _base AS (SELECT * FROM t) SELECT a FROM _base"
        rules = _lint(sql)
        assert "no-select-star-in-cte" in rules

    def test_no_warn_when_cte_lists_columns(self):
        sql = "WITH _base AS (SELECT a, b FROM t) SELECT a FROM _base"
        rules = _lint(sql)
        assert "no-select-star-in-cte" not in rules

    def test_no_warn_on_star_outside_cte(self):
        # SELECT * in the outer query is caught by no-select-star, not this rule
        sql = "WITH _base AS (SELECT a FROM t) SELECT * FROM _base"
        rules = _lint(sql, no_select_star="off")
        assert "no-select-star-in-cte" not in rules

    def test_off_disables_rule(self):
        sql = "WITH _base AS (SELECT * FROM t) SELECT a FROM _base"
        rules = _lint(sql, no_select_star_in_cte="off")
        assert "no-select-star-in-cte" not in rules

    def test_no_warn_count_star_in_cte(self):
        sql = "WITH _base AS (SELECT COUNT(*) AS n FROM t) SELECT n FROM _base"
        rules = _lint(sql)
        assert "no-select-star-in-cte" not in rules


class TestViolationPositions:
    """Verify that violations report line/column from node.meta, not None."""

    def _violations(self, sql: str, **overrides):
        config = JarifyConfig(**overrides)
        return lint_sql(sql, config)

    def test_no_select_star_has_position(self):
        violations = self._violations("SELECT * FROM t")
        v = next(v for v in violations if v.rule == "no-select-star")
        assert v.line is not None, "line should not be None"
        assert v.column is not None, "column should not be None"

    def test_no_unused_cte_has_position(self):
        violations = self._violations("WITH unused AS (SELECT 1 AS x) SELECT 2")
        v = next(v for v in violations if v.rule == "no-unused-cte")
        assert v.line is not None, "line should not be None"

    def test_cte_naming_has_position(self):
        violations = self._violations("WITH people AS (SELECT 1 AS id) SELECT id FROM people")
        v = next(v for v in violations if v.rule == "cte-naming")
        assert v.line is not None, "line should not be None"

    def test_prefer_using_over_on_has_position(self):
        violations = self._violations("SELECT a.x FROM a INNER JOIN b ON a.id = b.id")
        v = next(v for v in violations if v.rule == "prefer-using-over-on")
        assert v.line is not None, "line should not be None"

