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

    def test_set_min_column_alias_tracks_by_line(self):
        overrides = parse_comment_overrides(
            "-- jarify: set min-column-alias = 80\nSELECT 1 AS one, 22 AS two\n"
            "-- jarify: reset min-column-alias\nSELECT 3 AS three, 44 AS four\n"
        )

        config = JarifyConfig(min_column_alias=64)
        assert overrides.config_for_line(config, 2).min_column_alias == 80
        assert overrides.config_for_line(config, 4).min_column_alias == 64

    def test_set_min_column_alias_ignores_non_positive_values(self):
        overrides = parse_comment_overrides("-- jarify: set min-column-alias = 0\nSELECT 1 AS one, 2 AS two\n")

        config = JarifyConfig(min_column_alias=72)
        assert overrides.config_for_line(config, 2).min_column_alias == 72

    def test_set_min_column_alias_ignores_invalid_text_value(self):
        overrides = parse_comment_overrides("-- jarify: set min-column-alias = nope\nSELECT 1 AS one, 2 AS two\n")

        config = JarifyConfig(min_column_alias=72)
        assert overrides.config_for_line(config, 2).min_column_alias == 72

    def test_set_alias_visual_guide_interval_tracks_by_line(self):
        overrides = parse_comment_overrides(
            "-- jarify: set alias-visual-guide-interval = 12\nSELECT 1 AS one, 22 AS two\n"
            "-- jarify: reset alias-visual-guide-interval\nSELECT 3 AS three, 44 AS four\n"
        )

        config = JarifyConfig(alias_visual_guide_interval=16)
        assert overrides.config_for_line(config, 2).alias_visual_guide_interval == 12
        assert overrides.config_for_line(config, 4).alias_visual_guide_interval == 16

    def test_set_alias_visual_guide_interval_accepts_snake_case_name(self):
        overrides = parse_comment_overrides("-- jarify: set alias_visual_guide_interval = 12\nSELECT 1 AS one\n")

        assert overrides.config_for_line(JarifyConfig(), 2).alias_visual_guide_interval == 12

    def test_set_alias_visual_guide_interval_ignores_non_positive_values(self):
        overrides = parse_comment_overrides(
            "-- jarify: set alias-visual-guide-interval = 0\nSELECT 1 AS one, 2 AS two\n"
            "-- jarify: set alias-visual-guide-interval = -4\nSELECT 3 AS three, 4 AS four\n"
        )

        config = JarifyConfig(alias_visual_guide_interval=16)
        assert overrides.config_for_line(config, 2).alias_visual_guide_interval == 16
        assert overrides.config_for_line(config, 4).alias_visual_guide_interval == 16

    def test_set_alias_visual_guide_interval_ignores_invalid_text_value(self):
        overrides = parse_comment_overrides("-- jarify: set alias-visual-guide-interval = nope\nSELECT 1 AS one\n")

        config = JarifyConfig(alias_visual_guide_interval=16)
        assert overrides.config_for_line(config, 2).alias_visual_guide_interval == 16

    def test_set_boolean_option_parses_true_and_false(self):
        overrides = parse_comment_overrides(
            "-- jarify: set prefer-from-first = FALSE\nSELECT * FROM t\n"
            "-- jarify: set explicit_outer_join = True\nSELECT a FROM t LEFT JOIN u ON u.id = t.id\n"
        )

        config = overrides.config_for_line(JarifyConfig(), 4)
        assert config.prefer_from_first is False
        assert config.explicit_outer_join is True

    def test_set_boolean_option_ignores_other_values(self):
        overrides = parse_comment_overrides("-- jarify: set prefer-from-first = no\nSELECT * FROM t\n")

        assert overrides.config_for_line(JarifyConfig(), 2).prefer_from_first is True

    def test_set_ignores_unknown_and_list_options(self):
        overrides = parse_comment_overrides(
            "-- jarify: set no_such_option = 1\n-- jarify: set uppercase_functions = list\nSELECT 1\n"
        )

        assert overrides.config_for_line(JarifyConfig(), 3) == JarifyConfig()

    def test_set_parses_integer_options(self):
        overrides = parse_comment_overrides("-- jarify: set indent = 4\nSELECT 1\n")

        assert overrides.config_for_line(JarifyConfig(), 2).indent == 4

    def test_second_set_ends_the_first_range(self):
        overrides = parse_comment_overrides(
            "-- jarify: set explicit-outer-join = true\nSELECT 1\n;\n"
            "-- jarify: set explicit-outer-join = false\nSELECT 2\n"
        )

        config = JarifyConfig()
        assert overrides.config_for_line(config, 2).explicit_outer_join is True
        assert overrides.config_for_line(config, 5).explicit_outer_join is False


class TestLintOverrides:
    def test_disable_line_suppresses_inline_violation(self):
        sql = "SELECT * FROM t -- jarify: disable-line no-select-star"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_disable_next_line_suppresses_violation(self):
        sql = "-- jarify: disable-next-line no-select-star\nSELECT * FROM t"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_disable_next_line_suppresses_multiline_expression(self):
        # CASE spans multiple lines after formatting; the directive is on the line
        # before SELECT, so the violation must be suppressed across all body lines.
        sql = (
            "-- jarify: disable-next-line prefer-if-over-case\n"
            "SELECT\n"
            "   CASE\n"
            "     WHEN a > 1\n"
            "     THEN 'big'\n"
            "     ELSE 'small'\n"
            "   END\n"
            "FROM t\n"
            ";\n"
        )
        assert "prefer-if-over-case" not in _lint(sql)

    def test_disable_file_suppresses_entire_rule(self):
        sql = "-- jarify: disable-file no-select-star\nSELECT * FROM t\nSELECT * FROM u"
        assert "no-select-star" not in _lint(sql, prefer_from_first=False)

    def test_disable_next_line_suppresses_prefer_ifnull_over_coalesce(self):
        sql = "-- jarify: disable-next-line prefer-ifnull-over-coalesce\nSELECT coalesce(a, b) FROM t"
        assert "prefer-ifnull-over-coalesce" not in _lint(sql)

    def test_enable_restores_rule_after_region(self):
        sql = "-- jarify: disable no-select-star\nSELECT * FROM t;\n-- jarify: enable no-select-star\nSELECT * FROM u\n"
        assert _lint(sql, prefer_from_first=False) == ["no-select-star"]

    def test_disable_line_all_suppresses_every_rule(self):
        sql = "SELECT coalesce(a, b) FROM T -- jarify: disable-line all"
        assert _lint(sql, prefer_from_first=False) == []

    def test_disable_next_line_all_suppresses_every_rule(self):
        sql = "-- jarify: disable-next-line all\nSELECT coalesce(a, b) FROM T\n;\n"
        assert _lint(sql, prefer_from_first=False) == []

    def test_disable_file_all_suppresses_every_rule(self):
        sql = (
            "-- jarify: disable-file all\n"
            "SELECT * FROM t;\n"
            "SELECT coalesce(a, b) FROM u;\n"
        )
        assert _lint(sql, prefer_from_first=False) == []

    def test_disable_all_region_suppresses_every_rule(self):
        sql = (
            "-- jarify: disable all\n"
            "SELECT * FROM t;\n"
            "SELECT coalesce(a, b) FROM u;\n"
            "-- jarify: enable all\n"
            "SELECT * FROM v\n"
        )
        assert _lint(sql, prefer_from_first=False) == ["no-select-star"]

    def test_enable_all_closes_specific_open_disables(self):
        # `disable some-rule` followed by `enable all` should close the open
        # range, so violations after `enable all` are reported normally.
        sql = (
            "-- jarify: disable no-select-star\n"
            "SELECT * FROM t;\n"
            "-- jarify: enable all\n"
            "SELECT * FROM u\n"
        )
        assert _lint(sql, prefer_from_first=False) == ["no-select-star"]

    def test_disable_line_all_is_case_insensitive(self):
        sql = "SELECT coalesce(a, b) FROM T -- jarify: disable-line ALL"
        assert _lint(sql, prefer_from_first=False) == []

    def test_enable_specific_rule_inside_disable_all_is_noop(self):
        # Pin current behavior: `disable all` is range-keyed by "all", so
        # `enable some-rule` does not split the range. Document this rather
        # than silently change it.
        sql = (
            "-- jarify: disable all\n"
            "SELECT * FROM t;\n"
            "-- jarify: enable no-select-star\n"
            "SELECT * FROM u\n"
        )
        assert _lint(sql, prefer_from_first=False) == []


class TestFormatOverridesAll:
    def test_disable_next_line_all_preserves_multiple_rewrites(self):
        # Format-side coverage for `all`: a single statement that would trigger
        # several formatter rewrites must be left alone end-to-end.
        sql = (
            "-- jarify: disable-next-line all\n"
            "SELECT CASE WHEN a > 1 THEN 'big' ELSE 'small' END, coalesce(x, y) FROM t1, t2\n"
        )

        formatted, _ = format_sql(sql)

        assert "CASE" in formatted
        assert "if(" not in formatted
        assert "coalesce(x, y)" in formatted
        assert "ifnull(x, y)" not in formatted
        assert "CROSS JOIN" not in formatted


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

    def test_disable_next_line_preserves_two_arg_coalesce(self):
        sql = "-- jarify: disable-next-line prefer-ifnull-over-coalesce\nSELECT coalesce(a, b) FROM t"

        formatted, _ = format_sql(sql)

        assert "coalesce(a, b)" in formatted
        assert "ifnull(a, b)" not in formatted

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

    def test_set_min_column_alias_applies_to_following_statement(self):
        sql = "-- jarify: set min-column-alias = 24\nSELECT a AS one, bb AS two FROM t"

        formatted, _ = format_sql(sql)

        alias_lines = [line for line in formatted.splitlines() if " AS " in line]
        assert len({line.index(" AS ") for line in alias_lines}) == 1
        assert alias_lines[0].index(" AS ") == 24

    def test_reset_min_column_alias_restores_base_config_behavior(self):
        sql = (
            "-- jarify: set min-column-alias = 24\n"
            "SELECT a AS one, bb AS two FROM t;\n"
            "-- jarify: reset min-column-alias\n"
            "SELECT c AS three, dd AS four FROM t"
        )

        formatted, _ = format_sql(sql)

        alias_lines = [line for line in formatted.splitlines() if " AS " in line]
        assert alias_lines[0].index(" AS ") == 24
        assert alias_lines[1].index(" AS ") == 24
        assert alias_lines[2].index(" AS ") < 24
        assert alias_lines[3].index(" AS ") < 24

    def test_set_alias_visual_guide_interval_applies_to_following_statement(self):
        sql = "-- jarify: set alias-visual-guide-interval = 12\nSELECT customer_name AS name, id AS customer_id FROM t"

        formatted, _ = format_sql(sql)

        alias_lines = [line for line in formatted.splitlines() if " AS " in line]
        # AS starts in 1-based column 24, the first multiple of 12 at or after column 18.
        assert [line.index(" AS ") + 2 for line in alias_lines] == [24, 24]

    def test_reset_alias_visual_guide_interval_restores_base_config_behavior(self):
        sql = (
            "-- jarify: set alias-visual-guide-interval = 12\n"
            "SELECT customer_name AS name, id AS customer_id FROM t;\n"
            "-- jarify: reset alias-visual-guide-interval\n"
            "SELECT customer_name AS name, id AS customer_id FROM t"
        )

        formatted, _ = format_sql(sql)

        alias_lines = [line for line in formatted.splitlines() if " AS " in line]
        assert [line.index(" AS ") + 2 for line in alias_lines] == [24, 24, 18, 18]

    def test_alias_visual_guide_interval_and_min_column_alias_directives_compose(self):
        sql = (
            "-- jarify: set alias-visual-guide-interval = 12\n"
            "-- jarify: set min-column-alias = 34\n"
            "SELECT id AS order_id, status AS order_status FROM orders"
        )

        formatted, _ = format_sql(sql)

        alias_lines = [line for line in formatted.splitlines() if " AS " in line]
        assert [line.index(" AS ") + 2 for line in alias_lines] == [36, 36]

    def test_set_boolean_option_turns_it_off_until_reset(self):
        sql = (
            "-- jarify: set prefer-from-first = false\n"
            "SELECT * FROM t;\n"
            "-- jarify: reset prefer-from-first\n"
            "SELECT * FROM u"
        )

        formatted, _ = format_sql(sql)

        assert "SELECT\n   *\nFROM t\n;" in formatted
        assert "\nFROM u\n;" in formatted
        assert "*\nFROM u" not in formatted

    def test_set_explicit_outer_join_per_statement(self):
        sql = (
            "-- jarify: set explicit-outer-join = true\n"
            "SELECT a FROM t LEFT JOIN u ON u.id = t.id;\n"
            "-- jarify: set explicit-outer-join = false\n"
            "SELECT a FROM t LEFT OUTER JOIN u ON u.id = t.id"
        )

        formatted, _ = format_sql(sql)

        first, second = formatted.split("\n;\n", 1)
        assert "LEFT OUTER JOIN u" in first
        assert "LEFT JOIN u" in second

    def test_set_unknown_option_does_not_fail(self):
        formatted, warnings = format_sql("-- jarify: set no_such_option = 1\nSELECT a FROM t")

        assert not warnings
        assert "SELECT\n   a\nFROM t\n;" in formatted
