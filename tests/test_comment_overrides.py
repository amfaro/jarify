"""Tests for comment-based lint and format overrides."""

from __future__ import annotations

from jarify.comment_overrides import parse_comment_overrides
from jarify.config import JarifyConfig
from jarify.formatter import format_sql
from jarify.linter import lint_sql


def _lint(sql: str, **config_overrides) -> list[str]:
    config = JarifyConfig(**config_overrides)
    return [v.rule for v in lint_sql(sql, config)]


class TestOverrideParsing:
    def test_disable_region_tracks_until_enable(self):
        overrides = parse_comment_overrides(
            "-- jarify: disable no-select-star\nSELECT * FROM t\n-- jarify: enable no-select-star\nSELECT * FROM u\n"
        )

        assert overrides.is_rule_disabled("no-select-star", 2) is True
        assert overrides.is_rule_disabled("no-select-star", 4) is False

    def test_set_max_line_length_tracks_by_line(self):
        overrides = parse_comment_overrides(
            "-- jarify: set max_line_length = 200\nSELECT 1\n-- jarify: reset max_line_length\nSELECT 2\n"
        )

        config = JarifyConfig(max_line_length=40)
        assert overrides.config_for_line(config, 2).max_line_length == 200
        assert overrides.config_for_line(config, 4).max_line_length == 40


class TestLintOverrides:
    def test_disable_line_suppresses_inline_violation(self):
        sql = "SELECT * FROM t -- jarify: disable-line no-select-star"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_disable_next_line_suppresses_violation(self):
        sql = "-- jarify: disable-next-line no-select-star\nSELECT * FROM t"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_disable_file_suppresses_entire_rule(self):
        sql = "-- jarify: disable-file no-select-star\nSELECT * FROM t\nSELECT * FROM u"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_enable_restores_rule_after_region(self):
        sql = "-- jarify: disable no-select-star\nSELECT * FROM t;\n-- jarify: enable no-select-star\nSELECT * FROM u\n"
        assert _lint(sql, prefer_from_first=False) == ["no-select-star"]


class TestFormatOverrides:
    def test_disable_next_line_preserves_case_expression(self):
        sql = (
            "-- jarify: disable-next-line prefer-if-over-case\n"
            "SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END FROM t"
        )

        formatted, _ = format_sql(sql)

        assert "CASE" in formatted
        assert "if(" not in formatted

    def test_disable_next_line_preserves_comma_join(self):
        sql = "-- jarify: disable-next-line no-implicit-cross-join\nSELECT a FROM t1, t2"

        formatted, _ = format_sql(sql)

        assert "CROSS JOIN" not in formatted
        assert "FROM t1, t2" in formatted

    def test_disable_next_line_preserves_cte_name(self):
        sql = "-- jarify: disable-next-line cte-naming\nWITH people AS (SELECT 1 AS id) SELECT id FROM people"

        formatted, _ = format_sql(sql)

        assert "WITH people AS" in formatted
        assert "_people" not in formatted

    def test_set_max_line_length_applies_to_following_statement(self):
        sql = (
            "-- jarify: set max_line_length = 200\n"
            "SELECT if("
            "really_long_condition_name > 10, "
            "really_long_true_value_name, "
            "really_long_false_value_name"
            ") FROM t"
        )

        formatted, _ = format_sql(sql, JarifyConfig(max_line_length=40))

        assert (
            "if(really_long_condition_name > 10, really_long_true_value_name, really_long_false_value_name)"
            in formatted
        )
        assert "if(\n" not in formatted
