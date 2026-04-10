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
