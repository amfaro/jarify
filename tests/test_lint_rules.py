"""Tests for lint rules."""

from __future__ import annotations

from jarify.config import JarifyConfig
from jarify.linter import lint_sql


def _lint(sql: str, **config_overrides) -> list[str]:
    """Helper: lint SQL and return list of rule names that fired."""
    config = JarifyConfig(**config_overrides)
    return [v.rule for v in lint_sql(sql, config)]


class TestNoImplicitCrossJoin:
    def test_warns_on_comma_join(self):
        rules = _lint("SELECT a FROM t1, t2")
        assert "no-implicit-cross-join" in rules

    def test_no_warn_on_explicit_cross_join(self):
        rules = _lint("SELECT a FROM t1 CROSS JOIN t2")
        assert "no-implicit-cross-join" not in rules

    def test_no_warn_on_inner_join(self):
        rules = _lint("SELECT a FROM t1 INNER JOIN t2 ON t1.id = t2.id")
        assert "no-implicit-cross-join" not in rules

    def test_off_disables_lint(self):
        rules = _lint("SELECT a FROM t1, t2", no_implicit_cross_join="off")
        assert "no-implicit-cross-join" not in rules

    def test_autofix_rewrites_to_cross_join(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT a FROM t1, t2")
        assert "CROSS JOIN t2" in out
        assert "t1, t2" not in out

    def test_autofix_rewrites_multiple_comma_joins(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT a FROM t1, t2, t3")
        assert "CROSS JOIN t2" in out
        assert "CROSS JOIN t3" in out
        assert "," not in out.split("FROM")[1].split("WHERE")[0]

    def test_off_preserves_comma_join_in_fmt(self):
        from jarify.config import JarifyConfig
        from jarify.formatter import format_sql

        config = JarifyConfig(no_implicit_cross_join="off")
        out, _ = format_sql("SELECT a FROM t1, t2", config)
        assert "CROSS JOIN" not in out

    def test_formatted_sql_passes_lint(self):
        from jarify.formatter import format_sql

        formatted, _ = format_sql("SELECT a FROM t1, t2")
        rules = _lint(formatted)
        assert "no-implicit-cross-join" not in rules


class TestNoSelectStar:
    def test_warns_on_select_star(self):
        # prefer_from_first=False: formatter won't rewrite, so lint should warn
        rules = _lint("SELECT * FROM t", prefer_from_first=False)
        assert "no-select-star" in rules

    def test_no_warn_on_explicit_columns(self):
        rules = _lint("SELECT a, b FROM t")
        assert "no-select-star" not in rules

    def test_off_disables_rule(self):
        rules = _lint("SELECT * FROM t", no_select_star="off", prefer_from_first=False)
        assert "no-select-star" not in rules

    def test_count_star_not_flagged(self):
        rules = _lint("SELECT COUNT(*) FROM t")
        assert "no-select-star" not in rules

    def test_no_warn_on_from_first_when_prefer_from_first_enabled(self):
        # fmt rewrites SELECT * FROM t → FROM t when prefer_from_first=True.
        # Linting the formatted output must not re-fire no-select-star.
        rules = _lint("FROM t", prefer_from_first=True)
        assert "no-select-star" not in rules

    def test_no_warn_on_select_star_when_prefer_from_first_enabled(self):
        # SELECT * FROM single-table is what the formatter handles via FROM-first.
        # Both SELECT * FROM t and FROM t parse to the same AST, so linting
        # SELECT * FROM t should also not warn when prefer_from_first=True.
        rules = _lint("SELECT * FROM t", prefer_from_first=True)
        assert "no-select-star" not in rules

    def test_warns_on_select_star_with_joins_even_when_prefer_from_first_enabled(self):
        # SELECT * with joins is not a FROM-first candidate; still flag it.
        rules = _lint("SELECT * FROM t JOIN u ON t.id = u.id", prefer_from_first=True)
        assert "no-select-star" in rules

    def test_warns_when_prefer_from_first_disabled(self):
        # FROM t parses as SELECT * FROM t; should fire when prefer_from_first=False.
        rules = _lint("FROM t", prefer_from_first=False)
        assert "no-select-star" in rules


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

        config = JarifyConfig(no_select_star="error", prefer_from_first=False)
        violations = lint_sql("SELECT * FROM t", config)
        star_violations = [v for v in violations if v.rule == "no-select-star"]
        assert star_violations
        assert star_violations[0].severity == "error"

    def test_violation_str_includes_severity(self):
        from jarify.config import JarifyConfig
        from jarify.linter import lint_sql

        config = JarifyConfig(no_select_star="warn", prefer_from_first=False)
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
        violations = self._violations("SELECT * FROM t", prefer_from_first=False)
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


class TestPreferNeqOperator:
    def test_warns_on_diamond_operator(self):
        sql = "SELECT a FROM t WHERE x <> y"
        rules = _lint(sql)
        assert "prefer-neq-operator" in rules

    def test_warns_on_multiple_neq_expressions(self):
        sql = "SELECT a FROM t WHERE x <> y AND p <> q"
        rules = _lint(sql)
        assert rules.count("prefer-neq-operator") == 2

    def test_off_disables_rule(self):
        sql = "SELECT a FROM t WHERE x <> y"
        rules = _lint(sql, prefer_neq_operator="off")
        assert "prefer-neq-operator" not in rules


class TestRustFormatSyntax:
    """SQL files used as Rust format-string templates must not emit parse errors."""

    def test_clause_placeholder_no_parse_error(self):
        sql = "FROM examples\n{where_clause}\n;"
        rules = _lint(sql)
        assert "parse-error" not in rules

    def test_multiple_placeholders_no_parse_error(self):
        sql = "FROM {table_name}\n{where_clause}\n;"
        rules = _lint(sql)
        assert "parse-error" not in rules

    def test_other_lint_rules_still_fire(self):
        # no-select-star should still fire for explicit SELECT *
        sql = "SELECT * FROM examples\n{where_clause}\n;"
        rules = _lint(sql, prefer_from_first=False)
        assert "parse-error" not in rules
        assert "no-select-star" in rules

    def test_plain_invalid_sql_still_errors(self):
        # Non-template gibberish must still be caught
        rules = _lint("THIS IS NOT VALID SQL @@@!!!")
        assert "parse-error" in rules


class TestPreferIfOverCase:
    def test_warns_on_single_when_with_else(self):
        sql = "SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END FROM t"
        rules = _lint(sql)
        assert "prefer-if-over-case" in rules

    def test_warns_on_single_when_no_else(self):
        sql = "SELECT CASE WHEN b IS NULL THEN 0 END FROM t"
        rules = _lint(sql)
        assert "prefer-if-over-case" in rules

    def test_no_warn_on_multi_when(self):
        sql = "SELECT CASE WHEN a = 1 THEN 'one' WHEN a = 2 THEN 'two' END FROM t"
        rules = _lint(sql)
        assert "prefer-if-over-case" not in rules

    def test_no_warn_on_simple_case(self):
        sql = "SELECT CASE a WHEN 1 THEN 'one' ELSE 'other' END FROM t"
        rules = _lint(sql)
        assert "prefer-if-over-case" not in rules

    def test_no_warn_on_already_rewritten(self):
        sql = "SELECT if(a > 1, 'big', 'small') FROM t"
        rules = _lint(sql)
        assert "prefer-if-over-case" not in rules

    def test_off_disables_rule(self):
        sql = "SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END FROM t"
        rules = _lint(sql, prefer_if_over_case="off")
        assert "prefer-if-over-case" not in rules
