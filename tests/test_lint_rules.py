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
        # Ensure the message names the offender
        cte_msgs = [v.message for v in violations if v.rule == "cte-naming"]
        assert any("bad" in m for m in cte_msgs)

