"""Tests for the SQL formatter."""

import pytest

from jarify.config import JarifyConfig
from jarify.formatter import format_sql


def _alias_positions(sql: str, *aliases: str) -> list[int]:
    return [
        line.index(" AS ")
        for line in sql.splitlines()
        if any(f" AS {alias}" in line for alias in aliases)
    ]


def _as_columns(sql: str, *aliases: str) -> list[int]:
    """Return the 1-based editor column where each matching `AS` keyword starts."""
    return [position + 2 for position in _alias_positions(sql, *aliases)]


def test_format_simple_select():
    result, _ = format_sql("select 1")
    assert result.strip() != ""


def test_format_preserves_semantics():
    sql = "SELECT a, b FROM my_table WHERE x > 1"
    result, _ = format_sql(sql)
    # The formatted output should still be valid SQL containing the same elements
    assert "a" in result
    assert "b" in result
    assert "my_table" in result


def test_format_multiple_statements():
    sql = "SELECT 1; SELECT 2"
    result, _ = format_sql(sql)
    assert result.count(";") == 2


def test_format_respects_config():
    config = JarifyConfig(indent=4)
    result, _ = format_sql("SELECT a FROM b WHERE c = 1", config)
    assert result.strip() != ""


def test_semicolon_on_own_line():
    result, _ = format_sql("SELECT a FROM t")
    lines = result.splitlines()
    assert lines[-1].strip() == ";", f"Expected last line to be ';', got: {lines[-1]!r}"


def test_semicolon_own_line_multi_statement():
    sql = "SELECT 1; SELECT 2"
    result, _ = format_sql(sql)
    for line in result.splitlines():
        # No line should end with a semicolon — semicolons always on their own line
        stripped = line.rstrip()
        if stripped:
            assert not stripped.endswith(";") or stripped == ";", f"Semicolon at end of non-blank line: {stripped!r}"


def test_as_alignment():
    sql = "SELECT first_name AS first, last_name AS last, email AS email_address FROM t"
    result, _ = format_sql(sql)
    as_positions = _alias_positions(result, "first", "last", "email_address")
    assert len(set(as_positions)) == 1, f"AS keywords not aligned: {as_positions}"


def test_min_column_alias_pushes_aliases_to_configured_visible_column():
    sql = "SELECT a AS one, bb AS two FROM t"
    result, _ = format_sql(sql, JarifyConfig(min_column_alias=24))

    as_positions = _alias_positions(result, "one", "two")
    assert as_positions == [24, 24]


def test_min_column_alias_does_not_shrink_longer_alignment():
    sql = "SELECT a AS one, some_really_long_expression AS two FROM t"
    baseline, _ = format_sql(sql)
    result, _ = format_sql(sql, JarifyConfig(min_column_alias=12))

    assert _alias_positions(result, "one", "two") == _alias_positions(baseline, "one", "two")


def test_as_alignment_spans_ctes_and_outer_select():
    sql = (
        "WITH a AS (SELECT x AS first, yy AS second FROM t), "
        "b AS (SELECT zzz AS third, w AS fourth FROM u) "
        "SELECT q AS fifth, rr AS sixth FROM a JOIN b ON 1 = 1"
    )
    result, _ = format_sql(sql)
    as_positions = _alias_positions(result, "first", "second", "third", "fourth", "fifth", "sixth")
    assert len(set(as_positions)) == 1, f"AS keywords not aligned across query: {as_positions}"


def test_min_column_alias_applies_across_ctes_and_outer_select():
    sql = (
        "WITH a AS (SELECT x AS first, yy AS second FROM t), "
        "b AS (SELECT zzz AS third, w AS fourth FROM u) "
        "SELECT q AS fifth, rr AS sixth FROM a JOIN b ON 1 = 1"
    )
    result, _ = format_sql(sql, JarifyConfig(min_column_alias=28))

    as_positions = _alias_positions(result, "first", "second", "third", "fourth", "fifth", "sixth")
    assert len(set(as_positions)) == 1
    assert as_positions[0] >= 28


def test_as_alignment_stays_visually_consistent_across_nested_ctes():
    sql = (
        "WITH outer_group AS ("
        "  WITH seed_group AS ("
        "    SELECT alpha_value AS seed_one, beta_metric AS seed_two FROM source_a"
        "  )"
        "  SELECT seed_one AS outer_one, seed_two AS outer_two FROM seed_group"
        "), "
        "sibling_group AS ("
        "  SELECT gamma_code AS sibling_one, delta_indicator AS sibling_two FROM source_b"
        ") "
        "SELECT outer_one AS final_one, sibling_two AS final_two "
        "FROM outer_group JOIN sibling_group ON outer_one = sibling_one"
    )
    result, _ = format_sql(sql)
    as_positions = _alias_positions(
        result,
        "seed_one",
        "seed_two",
        "outer_one",
        "outer_two",
        "sibling_one",
        "sibling_two",
        "final_one",
        "final_two",
    )
    assert len(set(as_positions)) == 1, f"Nested CTE alias alignment drifted: {as_positions}"


class TestAliasVisualGuideInterval:
    def test_rounds_as_column_up_to_next_guide(self):
        # `customer_name` ends in column 16, so AS would otherwise start in column 18.
        sql = "SELECT customer_name AS name, id AS customer_id FROM customers"
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(baseline, "name", "customer_id") == [18, 18]
        assert _as_columns(result, "name", "customer_id") == [24, 24]

    def test_keeps_as_column_already_on_a_guide(self):
        sql = "SELECT lifetime_orders_cnt AS order_count, id AS customer_id FROM customer_stats"
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(baseline, "order_count", "customer_id") == [24, 24]
        assert result == baseline

    def test_moves_past_guide_when_longest_expression_needs_it(self):
        sql = "SELECT lifetime_orders_count AS order_count, id AS customer_id FROM customer_stats"
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(result, "order_count", "customer_id") == [36, 36]

    def test_rounds_up_after_min_column_alias_floor(self):
        config = JarifyConfig(min_column_alias=34, alias_visual_guide_interval=12)
        short, _ = format_sql("SELECT id AS order_id, status AS order_status FROM orders", config)
        long, _ = format_sql(
            "SELECT id AS order_id, ifnull(shipping_address, billing_address) AS address FROM orders", config
        )

        assert _as_columns(short, "order_id", "order_status") == [36, 36]
        assert _as_columns(long, "order_id", "address") == [48, 48]

    def test_applies_one_guide_column_across_nested_ctes(self):
        sql = (
            "WITH outer_group AS ("
            "  WITH seed_group AS ("
            "    SELECT alpha_value AS seed_one, beta_metric AS seed_two FROM source_a"
            "  )"
            "  SELECT seed_one AS outer_one, seed_two AS outer_two FROM seed_group"
            "), "
            "sibling_group AS ("
            "  SELECT gamma_code AS sibling_one, delta_indicator AS sibling_two FROM source_b"
            ") "
            "SELECT outer_one AS final_one, sibling_two AS final_two "
            "FROM outer_group JOIN sibling_group ON outer_one = sibling_one"
        )
        aliases = ("seed_one", "seed_two", "outer_one", "outer_two", "sibling_one", "sibling_two")
        aliases += ("final_one", "final_two")
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert set(_as_columns(baseline, *aliases)) == {22}
        assert _as_columns(result, *aliases) == [24] * len(aliases)

    def test_aligns_multiline_expression_by_its_closing_line(self):
        sql = (
            "SELECT c.id AS customer_id, "
            "CASE WHEN c.ltv > 100000 THEN 'gold' WHEN c.ltv > 10000 THEN 'silver' ELSE 'bronze' END AS tier "
            "FROM customers c"
        )
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        end_line = next(line for line in result.splitlines() if " AS tier" in line)
        assert end_line.lstrip().startswith("END")
        assert _as_columns(result, "customer_id", "tier") == [12, 12]

    def test_applies_to_subquery_with_local_alignment(self):
        sql = "SELECT x FROM t LEFT JOIN (SELECT p AS s1, some_long_thing AS s2 FROM u) s ON s.s1 = t.x"
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(baseline, "s1", "s2") == [22, 22]
        assert _as_columns(result, "s1", "s2") == [24, 24]

    def test_applies_to_each_locally_aligned_union_branch(self):
        sql = "SELECT p AS s1, qq AS s2 FROM u UNION ALL SELECT p AS s1, qqqqqq AS s2 FROM v"
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(baseline, "s1", "s2") == [7, 7, 11, 11]
        assert _as_columns(result, "s1", "s2") == [12, 12, 12, 12]

    def test_interval_of_one_matches_default_output(self):
        sql = (
            "WITH a AS (SELECT x AS first, CASE WHEN y THEN 1 ELSE 2 END AS second FROM t) "
            "SELECT * REPLACE (q + 1 AS q) RENAME (r AS renamed_r, s AS renamed_s), "
            "first AS one, second AS two FROM a JOIN (SELECT p AS s1, qq AS s2 FROM u) s ON s.s1 = a.first"
        )
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=1))

        assert result == baseline

    def test_leaves_table_alias_alignment_unchanged(self):
        sql = (
            "SELECT o.id AS order_id, c.name AS customer_name FROM orders o "
            "INNER JOIN customers c ON c.id = o.customer_id LEFT JOIN addresses addr ON addr.id = o.address_id"
        )
        baseline, _ = format_sql(sql)
        result, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        table_prefixes = ("FROM", "INNER JOIN", "LEFT JOIN")
        table_lines = [line for line in result.splitlines() if line.startswith(table_prefixes)]
        assert len(table_lines) == 3
        assert table_lines == [line for line in baseline.splitlines() if line.startswith(table_prefixes)]
        assert _as_columns(baseline, "order_id", "customer_name") == [11, 11]
        assert _as_columns(result, "order_id", "customer_name") == [12, 12]


def test_searched_case_issue_260_layout_is_preserved():
    sql = """SELECT
   foo_bar_baz AS xyz
  ,CASE
     WHEN foo
     THEN bar
     WHEN baz
      AND baq
     THEN world
     ELSE null
   END        AS abc
FROM data
;"""
    result, _ = format_sql(sql)
    assert "\n     WHEN foo\n     THEN bar\n" in result
    assert "\n     WHEN baz\n      AND baq\n     THEN world\n" in result
    assert "\n   END         AS abc\n" in result


def test_parse_failure_returns_original_with_warning():
    """Unparseable SQL is returned unchanged with a warning instead of crashing."""
    bad_sql = "THIS IS NOT VALID SQL @@@!!!"
    result, warnings = format_sql(bad_sql)
    assert result == bad_sql
    assert len(warnings) == 1
    assert "could not parse" in str(warnings[0])


def test_parse_failure_warning_includes_actual_error_not_pivot_message():
    """Warning for non-PIVOT parse failures must not mention PIVOT or issues/2."""
    bad_sql = "THIS IS NOT VALID SQL @@@!!!"
    _, warnings = format_sql(bad_sql)
    msg = str(warnings[0])
    assert "PIVOT" not in msg
    assert "issues/2" not in msg


def test_pivot_order_by_formats_without_warning():
    """PIVOT ... USING ... ORDER BY is formatted cleanly without any warning."""
    sql = (
        "WITH _d AS (SELECT a, grp, val FROM t) "
        "PIVOT (SELECT a, grp, val FROM _d) ON grp USING first(val) ORDER BY a, grp"
    )
    result, warnings = format_sql(sql)
    assert not warnings, f"Expected no warnings, got: {warnings}"
    assert "ORDER BY" in result
    assert "PIVOT" in result
    # Idempotent
    result2, _ = format_sql(result)
    assert result == result2


def test_wide_if_keeps_condition_compact_but_wraps_overlong_true_branch():
    sql = (
        "SELECT if((ir.incentive_data->'transform'->>'type') IS NOT NULL, "
        "((ir.incentive_data->'transform'->>'type'), "
        "(ir.incentive_data->'transform'->>'from'), "
        "(ir.incentive_data->'transform'->>'based_on'))::transform, NULL) AS transform"
    )
    result, _ = format_sql(sql)
    assert "(ir.incentive_data->'transform'->>'type') IS NOT NULL\n     ,(" in result
    assert "\n        ,(ir.incentive_data->'transform'->>'from')" in result
    assert "\n     ,NULL" in result


def test_cast_wraps_json_extract_before_shorthand_cast():
    sql = "SELECT CAST(j->'x' AS STRUCT(a INTEGER)), CAST(j->>'label' AS TEXT) FROM t"
    result, _ = format_sql(sql)
    assert "(j->'x')::struct(a int)" in result
    assert "(j->>'label')::text" in result


def test_dynamic_json_extract_path_keeps_function_call_syntax():
    sql = (
        "SELECT json_extract_string("
        "to_json(struct_pack(purchaser := ft.purchaser)), "
        "concat('$.', o.group_by_field, '.', o.group_by_key)) "
        "FROM offers o JOIN fact_transactions ft ON o.id = ft.offer_id"
    )
    result, _ = format_sql(sql)
    assert "json_extract_string(" in result
    assert "->>concat(" not in result


def test_transform_macro_is_not_rewritten_to_list_transform():
    sql = "SELECT transform(t, _transform) AS incentivized_amount FROM txns"
    result, _ = format_sql(sql)
    assert "transform(t, _transform) AS incentivized_amount" in result
    assert "list_transform" not in result


def test_leading_comment_inside_or_group_stays_on_its_own_line():
    sql = """SELECT *
FROM t
WHERE 1 = 1
  AND (
    -- No prior-year baseline: infinite YoY improvement → highest tier
    (t.qualification_met AND t.qualification_target = 0)
    OR t.threshold_value >= r.threshold
  )
"""
    result, _ = format_sql(sql)
    preserved_branch = (
        "-- No prior-year baseline: infinite YoY improvement → highest tier\n"
        "    (t.qualification_met AND t.qualification_target = 0)"
    )
    assert preserved_branch in result
    swallowed_or = (
        "-- No prior-year baseline: infinite YoY improvement → highest tier OR t.threshold_value >= r.threshold"
    )
    assert swallowed_or not in result
    assert "OR t.threshold_value >= r.threshold" in result


def test_own_line_comment_without_space_after_dashes_stays_on_its_own_line():
    spaced, _ = format_sql("SELECT\n   a\n  -- ,b\n  ,c\nFROM t\n")
    unspaced, _ = format_sql("SELECT\n   a\n  --,b\n  ,c\nFROM t\n")
    assert unspaced == spaced
    assert "   a\n  -- ,b\n  ,c\n" in unspaced


def _lines_continuing_after_line_comment(sql: str) -> list[str]:
    """Return lines where something follows a ``--`` comment on the same line."""
    return [line for line in sql.splitlines() if "-- " in line and "--" in line.split("-- ", 1)[1]]


def test_several_comments_on_one_node_each_end_their_line():
    sql = "SELECT a /* first */ /* second */ AS c, b FROM t GROUP BY a /* g1 */ /* g2 */;\n"
    result, _ = format_sql(sql)
    assert "   a AS c -- first\n  -- second\n  ,b\n" in result
    assert "   a -- g1\n  -- g2\n;" in result
    assert not _lines_continuing_after_line_comment(result)
    assert format_sql(result)[0] == result


def test_several_comments_on_a_cte_go_above_it_one_per_line():
    sql = "WITH _a AS (SELECT 1 AS x)\n/* one */\n/* two */\n,_b AS (SELECT 2 AS y)\nSELECT x, y FROM _a, _b\n"
    result, _ = format_sql(sql)
    assert ")\n-- one\n-- two\n,_b AS\n(" in result
    assert format_sql(result)[0] == result


def test_pivot_order_by_keeps_cte_leading_comments_on_their_own_lines():
    """The PIVOT ... ORDER BY workaround must classify leading comments too."""
    sql = (
        "WITH _d AS (SELECT a, grp, val FROM t)\n"
        "-- first\n"
        "-- second\n"
        ",_e AS (SELECT a, grp, val FROM _d)\n"
        "PIVOT _e ON grp USING first(val) ORDER BY a"
    )
    result, warnings = format_sql(sql)
    assert not warnings
    assert ")\n-- first\n-- second\n,_e AS\n(" in result
    assert not _lines_continuing_after_line_comment(result)


class TestCommentsAfterLastStatement:
    """Comments after the last statement come out as written, after its ``;``.

    Regression: they were joined onto one line, so a ``--`` comment commented
    out the ``/*`` of a following block comment and its contents became SQL,
    and a stray ``;`` was added after them.
    """

    def test_comments_after_semicolon_are_kept_as_written(self):
        tail = "\n\n-- one\n\n-- two\n\n/*\nSELECT b\nFROM u\n*/\n"
        result, _ = format_sql("SELECT a FROM t\n;" + tail)
        assert result == "SELECT\n   a\nFROM t\n;" + tail

    def test_block_comment_after_semicolon_is_unchanged(self):
        formatted = "SELECT\n   a\nFROM t\n;\n\n\n/*\n  FROM t\n  LIMIT 1000\n  ;\n*/\n"
        result, _ = format_sql("SELECT a FROM t\n;\n\n\n/*\n  FROM t\n  LIMIT 1000\n  ;\n*/\n")
        assert result == formatted
        assert format_sql(formatted)[0] == formatted

    def test_comment_on_the_semicolon_line_stays_there(self):
        result, _ = format_sql("SELECT a FROM t; -- note\n\n-- more\n")
        assert result == "SELECT\n   a\nFROM t\n; -- note\n\n-- more\n"

    def test_comments_after_statement_without_semicolon_follow_the_added_semicolon(self):
        result, _ = format_sql("SELECT a FROM t -- note\n\n-- FROM t LIMIT 10\n")
        assert result == "SELECT\n   a\nFROM t -- note\n;\n\n-- FROM t LIMIT 10\n"
        assert format_sql(result)[0] == result

    def test_block_comment_on_the_last_line_stays_with_the_statement(self):
        result, _ = format_sql("SELECT a FROM t /* spans\nlines */\n-- after\n")
        assert result == "SELECT\n   a\nFROM t /* spans\nlines */\n;\n-- after\n"

    def test_comment_only_input_is_kept(self):
        sql = "-- nothing to format yet\n\n/* SELECT 1 */\n"
        assert format_sql(sql)[0] == sql


class TestBlockCommentLines:
    """A multi-line block comment's lines stay exactly as written.

    Regression: enclosing blocks indented the comment's own lines, so every
    pass shifted them two more columns to the right.
    """

    def test_commented_out_columns_in_a_cte_body_keep_their_lines(self):
        sql = (
            "WITH _m AS\n(\n  SELECT\n     a\n    ,b\n"
            "    /* add in for testing\n    ,c AS cc\n    */\n"
            "  FROM t\n)\nFROM _m\n;\n"
        )
        result, _ = format_sql(sql)
        assert "\n  /* add in for testing\n    ,c AS cc\n    */\n  FROM t\n" in result
        assert format_sql(result)[0] == result

    def test_commented_out_columns_between_columns_keep_their_lines(self):
        sql = "SELECT\n   a\n  /* testing\n  ,b\n  */\n  ,d\nFROM t\n;\n"
        result, _ = format_sql(sql)
        assert "   a /* testing\n  ,b\n  */\n  ,d\n" in result
        assert format_sql(result)[0] == result

    def test_comment_lines_without_leading_space_are_kept(self):
        sql = "WITH _m AS (\n  SELECT a\n  /* note\nflush left\n\t tabbed\n*/\n  FROM t\n)\nFROM _m;\n"
        result, _ = format_sql(sql)
        assert "/* note\nflush left\n\t tabbed\n*/\n  FROM t\n" in result
        assert format_sql(result)[0] == result

    def test_pivot_order_by_comment_lines_are_kept(self):
        sql = "WITH _d AS (SELECT a, grp, val FROM t)\nPIVOT _d ON grp USING first(val) ORDER BY a /* o\n   p */"
        result, warnings = format_sql(sql)
        assert not warnings
        assert "ORDER BY\n   a /* o\n   p */\n;" in result
        assert format_sql(result)[0] == result


def test_searched_case_puts_then_on_its_own_line_and_expands_connectors():
    sql = "SELECT CASE WHEN foo THEN bar WHEN baz AND baq THEN world ELSE NULL END AS abc FROM data"
    result, _ = format_sql(sql)
    assert "WHEN foo\n     THEN bar" in result
    assert "WHEN baz\n      AND baq\n     THEN world" in result
    assert "ELSE NULL" in result


def test_searched_case_right_aligns_or_with_and():
    sql = "SELECT CASE WHEN foo THEN bar WHEN baz OR hello THEN world ELSE NULL END AS abc FROM data"
    result, _ = format_sql(sql)
    assert "WHEN baz\n       OR hello\n     THEN world" in result


def _assert_comments_end_their_lines(result: str, *comments: str) -> None:
    """Each comment appears exactly once, with no SQL after it on its line (#251)."""
    for comment in comments:
        lines = [line for line in result.splitlines() if f"-- {comment}" in line]
        assert len(lines) == 1, f"comment {comment!r} missing or duplicated in:\n{result}"
        assert lines[0].endswith(f"-- {comment}"), f"SQL follows comment {comment!r}: {lines[0]!r}"


class TestConditionComments:
    def test_trailing_comments_after_is_not_null_survive(self):
        sql = "SELECT a FROM t\nWHERE a IS NOT NULL -- first\n   OR b IS NOT NULL -- second\n"
        result, _ = format_sql(sql)
        assert "WHERE a IS NOT NULL -- first\n   OR b IS NOT NULL -- second\n;" in result

    def test_single_commented_condition_keeps_its_comment(self):
        result, _ = format_sql("SELECT a FROM t\nWHERE a IS NOT NULL -- only\n")
        assert "WHERE a IS NOT NULL -- only\n;" in result

    def test_trailing_comment_on_parenthesized_branch_survives(self):
        sql = """SELECT a FROM t
WHERE a.allocation_per_year IS NOT NULL --eligible_for_allocation = 1
   OR nr.nominee_user_id IS NOT NULL     --has_points_spend = 1
   OR (h.rollup_level_id = 0 AND te.user_id IS NOT NULL)  --manager whose team is eligible
"""
        result, _ = format_sql(sql)
        assert (
            "WHERE a.allocation_per_year IS NOT NULL -- eligible_for_allocation = 1\n"
            "   OR nr.nominee_user_id IS NOT NULL -- has_points_spend = 1\n"
            "   OR (h.rollup_level_id = 0 AND te.user_id IS NOT NULL) -- manager whose team is eligible\n"
        ) in result

    def test_own_line_comment_before_or_lines_up_with_or(self):
        sql = "SELECT a FROM t\nWHERE a IS NOT NULL\n  -- first\n   OR b IS NOT NULL\n"
        result, _ = format_sql(sql)
        assert "WHERE a IS NOT NULL\n   -- first\n   OR b IS NOT NULL\n" in result

    def test_own_line_comment_before_and_lines_up_with_and(self):
        sql = "SELECT a FROM t\nWHERE a > 1\n  -- first\n  AND b > 2\n  -- second\n  AND c > 3\n"
        result, _ = format_sql(sql)
        assert "WHERE a > 1\n  -- first\n  AND b > 2\n  -- second\n  AND c > 3\n" in result

    def test_comment_after_connector_moves_above_it(self):
        result, _ = format_sql("SELECT a FROM t\nWHERE a = 1 OR -- after\n  b = 2\n")
        assert "WHERE a = 1\n   -- after\n   OR b = 2\n" in result

    def test_trailing_comment_on_nested_paren_does_not_swallow_or(self):
        sql = "SELECT a FROM t\nWHERE a = 1 AND ((b = 2) -- b branch\n OR d = 3)\n"
        result, _ = format_sql(sql)
        assert "(b = 2) -- b branch\n    OR d = 3\n" in result
        _assert_comments_end_their_lines(result, "b branch")

    def test_paren_in_comment_does_not_break_connector_alignment(self):
        sql = "SELECT a FROM t\nWHERE a > 1 -- see (1\n   OR b > 2 -- 2)\n   OR c > 3\n"
        result, _ = format_sql(sql)
        assert "WHERE a > 1 -- see (1\n   OR b > 2 -- 2)\n   OR c > 3\n" in result

    def test_uncommented_condition_is_unchanged(self):
        result, _ = format_sql("SELECT a FROM t WHERE a IS NOT NULL OR b IS NOT NULL")
        assert "WHERE a IS NOT NULL OR b IS NOT NULL\n" in result

    def test_having_comments_survive(self):
        sql = "SELECT a, COUNT(*) AS n FROM t GROUP BY a\nHAVING COUNT(*) > 1 -- first\n  -- own\n   OR a IS NOT NULL\n"
        result, _ = format_sql(sql)
        assert "HAVING COUNT(*) > 1 -- first\n    -- own\n    OR a IS NOT NULL\n" in result

    def test_qualify_comments_survive(self):
        sql = (
            "SELECT a FROM t\n"
            "QUALIFY row_number() OVER (ORDER BY b) = 1 -- latest\n"
            "  -- own\n"
            "  AND a IS NOT NULL -- present\n"
        )
        result, _ = format_sql(sql)
        _assert_comments_end_their_lines(result, "latest", "own", "present")
        assert "-- own\n  AND a IS NOT NULL -- present\n" in result

    def test_commented_join_on_breaks_onto_lines_aligned_after_on(self):
        sql = "SELECT a.x FROM a\nJOIN b ON a.id = b.id -- first\n  -- own\n  AND a.k IS NOT NULL -- second\n"
        result, _ = format_sql(sql)
        expected = "\n".join(
            [
                "INNER JOIN b ON a.id = b.id -- first",
                "            -- own",
                "            AND a.k IS NOT NULL -- second",
            ]
        )
        assert expected in result

    def test_single_commented_join_on_condition_stays_inline(self):
        result, _ = format_sql("SELECT a.x FROM a\nLEFT JOIN b ON a.id = b.id -- only\n")
        assert "LEFT JOIN b ON a.id = b.id -- only\n" in result

    def test_case_when_condition_comments_survive(self):
        sql = "SELECT CASE WHEN a > 0 -- first\n  -- own\n  OR b > 1 THEN 1 WHEN c = 2 THEN 3 END AS c FROM t\n"
        result, _ = format_sql(sql)
        assert "WHEN a > 0 -- first\n       -- own\n       OR b > 1\n     THEN 1" in result

    def test_single_when_case_with_comments_is_not_rewritten_to_if(self):
        sql = "SELECT CASE WHEN a IS NOT NULL -- first\n AND b > 1 THEN 1 ELSE 2 END AS c FROM t\n"
        result, _ = format_sql(sql)
        assert "if(" not in result
        assert "WHEN a IS NOT NULL -- first\n      AND b > 1\n     THEN 1" in result

    def test_commented_in_subquery_uses_block_form(self):
        sql = "SELECT a FROM t WHERE x IN (SELECT y FROM u WHERE y IS NOT NULL -- keep\n OR z = 1)\n"
        result, _ = format_sql(sql)
        assert "WHERE x IN\n(\n" in result
        assert "  WHERE y IS NOT NULL -- keep\n     OR z = 1\n)" in result

    def test_commented_from_subquery_is_not_inlined(self):
        sql = "SELECT a FROM (SELECT a FROM u WHERE a IS NOT NULL -- keep\n AND b = 1) s\n"
        result, _ = format_sql(sql)
        assert "  WHERE a IS NOT NULL -- keep\n    AND b = 1\n) AS s" in result

    def test_commented_if_condition_uses_expanded_form(self):
        result, _ = format_sql("SELECT if(a IS NOT NULL -- has a\n, 1, 2) AS x FROM t\n")
        assert "if(\n      a IS NOT NULL -- has a\n     ,1\n     ,2\n  ) AS x" in result


class TestFromFirst:
    def test_select_star_becomes_from_first(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT * FROM people")
        assert out.startswith("FROM people")
        assert "SELECT" not in out

    def test_select_star_with_where(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT * FROM people WHERE age > 18")
        assert "FROM people" in out
        assert "SELECT" not in out

    def test_select_star_with_join_keeps_select(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT * FROM people LEFT JOIN orders ON people.id = orders.person_id")
        assert "SELECT" in out

    def test_select_distinct_star_keeps_select(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT DISTINCT * FROM people")
        assert "SELECT DISTINCT" in out

    def test_explicit_columns_unaffected(self):
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT id, name FROM people")
        assert "SELECT" in out

    def test_prefer_from_first_false_keeps_select(self):
        from jarify.config import JarifyConfig
        from jarify.formatter import format_sql

        out, _ = format_sql("SELECT * FROM people", JarifyConfig(prefer_from_first=False))
        assert "SELECT" in out

    def test_modified_star_keeps_select_and_expands_modifiers(self):
        out, _ = format_sql(
            "SELECT * EXCLUDE (a, b) REPLACE (x + 1 AS x, y + 2 AS y) "
            "RENAME (old_name AS new_name, legacy_name AS display_name) FROM people"
        )
        assert out.startswith("SELECT")
        assert "FROM people" in out
        assert "   *\n   EXCLUDE (\n      a\n     ,b\n   )" in out
        assert "   REPLACE (\n      x + 1 AS x\n     ,y + 2 AS y\n   )" in out
        assert "   RENAME (\n      old_name    AS new_name\n     ,legacy_name AS display_name\n   )" in out

    def test_modified_star_aligns_aliases_within_replace_and_rename(self):
        out, _ = format_sql(
            "SELECT * REPLACE (id + 1 AS vendor_id, name || suffix AS vendor_name) "
            "RENAME (id AS vendor_id, name AS vendor_name) FROM vendors"
        )
        assert "      id + 1         AS vendor_id\n     ,name || suffix AS vendor_name" in out
        assert "      id   AS vendor_id\n     ,name AS vendor_name" in out

    def test_modified_star_respects_min_column_alias(self):
        out, _ = format_sql(
            "SELECT * REPLACE (id AS vendor_id, name AS vendor_name) "
            "RENAME (id AS display_id, name AS display_name) FROM vendors",
            JarifyConfig(min_column_alias=24),
        )

        replace_rename_lines = [line for line in out.splitlines() if " AS vendor_" in line or " AS display_" in line]
        assert len({line.index(" AS ") for line in replace_rename_lines}) == 1
        assert replace_rename_lines[0].index(" AS ") == 24

    def test_modified_star_respects_alias_visual_guide_interval(self):
        sql = (
            "SELECT * REPLACE (id + 1 AS vendor_id, name || suffix AS vendor_name) "
            "RENAME (id AS display_id, name AS display_name) FROM vendors"
        )
        baseline, _ = format_sql(sql)
        out, _ = format_sql(sql, JarifyConfig(alias_visual_guide_interval=12))

        assert _as_columns(baseline, "vendor_id", "vendor_name") == [22, 22]
        assert _as_columns(out, "vendor_id", "vendor_name") == [24, 24]
        # RENAME already lands on the column-12 guide, so it stays put.
        assert _as_columns(baseline, "display_id", "display_name") == [12, 12]
        assert _as_columns(out, "display_id", "display_name") == [12, 12]


class TestLeftOuterJoinNormalization:
    def test_left_outer_join_normalized(self):
        out, _ = format_sql("SELECT a FROM foo LEFT OUTER JOIN bar ON foo.id = bar.id")
        assert "LEFT JOIN" in out
        assert "LEFT OUTER JOIN" not in out

    def test_right_outer_join_normalized(self):
        out, _ = format_sql("SELECT a FROM foo RIGHT OUTER JOIN bar ON foo.id = bar.id")
        assert "RIGHT JOIN" in out
        assert "RIGHT OUTER JOIN" not in out

    def test_left_join_unchanged(self):
        out, _ = format_sql("SELECT a FROM foo LEFT JOIN bar ON foo.id = bar.id")
        assert "LEFT JOIN" in out

    def test_full_outer_join_preserved(self):
        out, _ = format_sql("SELECT a FROM foo FULL OUTER JOIN bar ON foo.id = bar.id")
        assert "FULL" in out


class TestExplicitOuterJoin:
    """explicit_outer_join = true writes OUTER on LEFT/RIGHT joins instead of dropping it."""

    CONFIG = JarifyConfig(explicit_outer_join=True)

    @pytest.mark.parametrize(
        ("join", "expected"),
        [
            ("LEFT JOIN bar ON foo.id = bar.id", "LEFT OUTER JOIN bar ON foo.id = bar.id"),
            ("RIGHT JOIN bar ON foo.id = bar.id", "RIGHT OUTER JOIN bar ON foo.id = bar.id"),
            ("LEFT OUTER JOIN bar ON foo.id = bar.id", "LEFT OUTER JOIN bar ON foo.id = bar.id"),
            ("RIGHT OUTER JOIN bar ON foo.id = bar.id", "RIGHT OUTER JOIN bar ON foo.id = bar.id"),
            ("LEFT JOIN bar USING (id)", "LEFT OUTER JOIN bar USING (id)"),
            ("NATURAL LEFT JOIN bar", "NATURAL LEFT OUTER JOIN bar"),
            (
                "ASOF LEFT JOIN bar ON foo.id = bar.id AND foo.ts >= bar.ts",
                "ASOF LEFT OUTER JOIN bar ON foo.id = bar.id AND foo.ts >= bar.ts",
            ),
            (
                "ASOF RIGHT JOIN bar ON foo.id = bar.id AND foo.ts >= bar.ts",
                "ASOF RIGHT OUTER JOIN bar ON foo.id = bar.id AND foo.ts >= bar.ts",
            ),
        ],
    )
    def test_left_and_right_joins_get_outer(self, join: str, expected: str):
        out, _ = format_sql(f"SELECT a FROM foo {join}", self.CONFIG)
        assert f"\n{expected}\n" in out

    @pytest.mark.parametrize(
        "join",
        [
            "INNER JOIN bar ON foo.id = bar.id",
            "FULL OUTER JOIN bar ON foo.id = bar.id",
            "FULL JOIN bar ON foo.id = bar.id",
            "CROSS JOIN bar",
            "SEMI JOIN bar ON foo.id = bar.id",
            "ANTI JOIN bar ON foo.id = bar.id",
            "POSITIONAL JOIN bar",
            "NATURAL JOIN bar",
            "ASOF JOIN bar ON foo.id = bar.id AND foo.ts >= bar.ts",
        ],
    )
    def test_other_joins_unchanged(self, join: str):
        default, _ = format_sql(f"SELECT a FROM foo {join}")
        out, _ = format_sql(f"SELECT a FROM foo {join}", self.CONFIG)
        assert out == default
        assert f"\n{join}\n" in out

    def test_bare_join_still_becomes_inner_join(self):
        out, _ = format_sql("SELECT a FROM foo JOIN bar ON foo.id = bar.id", self.CONFIG)
        assert "\nINNER JOIN bar ON foo.id = bar.id\n" in out

    def test_alias_alignment_measures_outer_keyword(self):
        sql = (
            "SELECT a FROM orders AS o LEFT JOIN users AS u ON u.id = o.user_id"
            " INNER JOIN addresses AS a ON a.id = o.aid"
        )
        out, _ = format_sql(sql, self.CONFIG)
        assert (
            "FROM orders           o\n"
            "LEFT OUTER JOIN users u ON u.id = o.user_id\n"
            "INNER JOIN addresses  a ON a.id = o.aid\n"
        ) in out

    def test_output_is_stable_on_second_pass(self):
        out, _ = format_sql("SELECT a FROM foo AS f LEFT JOIN bar AS b ON f.id = b.id", self.CONFIG)
        again, _ = format_sql(out, self.CONFIG)
        assert again == out


class TestJoinFormatting:
    def test_on_condition_inline(self):
        out, _ = format_sql("SELECT a FROM foo LEFT JOIN bar ON foo.id = bar.id")
        # ON must be on the same line as the JOIN, not on a new indented line
        assert "LEFT JOIN bar ON foo.id = bar.id" in out

    def test_on_multi_condition_inline(self):
        out, _ = format_sql("SELECT a FROM foo JOIN bar ON foo.id = bar.id AND foo.x = bar.x")
        assert "INNER JOIN bar ON foo.id = bar.id AND foo.x = bar.x" in out

    def test_as_omitted_from_join_table_alias(self):
        out, _ = format_sql("SELECT a FROM foo AS f LEFT JOIN bar AS b ON f.id = b.fid")
        assert " AS f" not in out
        assert " AS b" not in out
        lines = out.splitlines()
        from_line = next(ln for ln in lines if ln.startswith("FROM"))
        join_line = next(ln for ln in lines if "JOIN" in ln)
        assert from_line.startswith("FROM foo") and " f" in from_line
        assert "bar" in join_line and (" b " in join_line or join_line.endswith(" b"))

    def test_alias_alignment_applied(self):
        out, _ = format_sql(
            "SELECT a FROM orders AS o LEFT JOIN users AS u ON u.id = o.user_id"
            " LEFT JOIN addresses AS addr ON addr.id = o.aid"
        )
        lines = out.splitlines()
        from_line = next(ln for ln in lines if ln.startswith("FROM"))
        join_lines = [ln for ln in lines if "JOIN" in ln]

        def alias_col(line: str, alias: str) -> int:
            cutoff = line.index(" ON ") if " ON " in line else len(line)
            idx = line[:cutoff].rindex(f" {alias}")
            return idx + 1  # 0-based column of alias first char

        o_col = alias_col(from_line, "o")
        u_col = alias_col(join_lines[0], "u")
        addr_col = alias_col(join_lines[1], "addr")
        # End-alignment: the END of each alias lands at the same column.
        o_end = o_col + len("o")
        u_end = u_col + len("u")
        addr_end = addr_col + len("addr")
        assert o_end == u_end == addr_end, f"Alias end columns differ: o={o_end}, u={u_end}, addr={addr_end}"

    def test_no_alignment_with_subquery_join(self):
        out, _ = format_sql("SELECT a FROM t CROSS JOIN (SELECT b FROM s) AS sub LEFT JOIN u AS x ON x.id = t.id")
        # Subquery in block disables alignment but AS stays on subquery
        assert "CROSS JOIN" in out
        # Simple table alias still drops AS even without alignment
        assert "LEFT JOIN u x" in out

    def test_using_inline(self):
        out, _ = format_sql("SELECT a FROM foo JOIN bar USING (id)")
        assert "INNER JOIN bar USING (id)" in out


class TestGroupByPerLine:
    def test_group_by_multi_column_one_per_line(self):
        # When all non-agg columns are in GROUP BY, the formatter rewrites to GROUP BY ALL.
        out, _ = format_sql("SELECT a, b, count(*) FROM t GROUP BY a, b")
        assert "GROUP BY ALL" in out

    def test_group_by_explicit_when_partial(self):
        # When only a subset of non-agg columns is listed, keep explicit GROUP BY.
        out, _ = format_sql("SELECT a, b, c, count(*) FROM t GROUP BY a, b")
        lines = out.splitlines()
        group_by_idx = next(i for i, line in enumerate(lines) if "GROUP BY" in line)
        group_by_line = lines[group_by_idx]
        assert group_by_line.strip() == "GROUP BY", f"Expected 'GROUP BY' on its own line, got: {group_by_line!r}"

    def test_group_by_all_stays_inline(self):
        out, _ = format_sql("SELECT a, b, count(*) FROM t GROUP BY ALL")
        assert "GROUP BY ALL" in out

    def test_group_by_mixed_agg_expr_stays_explicit(self):
        sql = (
            "SELECT 'prefix: ' || group_field || string_agg(transaction_id, ', ') || "
            "group_key FROM t GROUP BY group_field, group_key"
        )
        out, _ = format_sql(sql)
        assert "GROUP BY ALL" not in out
        assert "group_field" in out
        assert "group_key" in out

    def test_group_by_single_column(self):
        out, _ = format_sql("SELECT a, count(*) FROM t GROUP BY a")
        assert "GROUP BY" in out
        assert "a" in out


class TestOrderByAll:
    def test_order_by_all_stays_inline(self):
        out, _ = format_sql("SELECT * FROM data ORDER BY ALL")
        assert "ORDER BY ALL" in out
        assert "ORDER BY\n" not in out


class TestTrailingRustFmtPlaceholder:
    """Trailing whole-line Rust format placeholders must land *before* the
    statement-terminating semicolon, not after it.

    Regression for: formatter inserts ';' between the last SQL clause and a
    trailing {placeholder}, producing invalid SQL when Rust substitutes a
    non-empty value (e.g. 'WHERE seller_key = ...').
    """

    def test_placeholder_before_semicolon(self):
        sql = "SELECT a, b\nFROM t\n{filter}"
        out, _ = format_sql(sql)
        lines = out.splitlines()
        filter_idx = next(i for i, line in enumerate(lines) if "{filter}" in line)
        semi_idx = next(i for i, line in enumerate(lines) if line.strip() == ";")
        assert filter_idx < semi_idx, f"{{filter}} (line {filter_idx}) must appear before ';' (line {semi_idx}):\n{out}"

    def test_idempotent(self):
        sql = "SELECT a, b\nFROM t\n{filter}"
        out, _ = format_sql(sql)
        out2, _ = format_sql(out)
        assert out == out2, f"Formatting is not idempotent:\nFirst pass:\n{out}\nSecond pass:\n{out2}"


class TestSQLMeshFormatting:
    def test_model_header_preserved_and_body_formatted(self):
        header = "MODEL (\n  name foo.bar,\n  kind FULL\n);\n\n"
        sql = header + "select a,b from t where x=1\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert out.startswith(header)
        assert "SELECT\n   a\n  ,b\nFROM t\nWHERE x = 1\n;\n" in out

    def test_audit_header_preserved_and_body_formatted(self):
        header = "AUDIT (\n  name assert_positive,\n);\n"
        sql = header + "select * from tbl where amount<0\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert out.startswith(header)
        assert "FROM tbl\nWHERE amount < 0\n;\n" in out

    def test_sqlmesh_macro_vars_survive_formatting(self):
        sql = "MODEL (name foo.bar);\nselect a from t where ds between @start_dt and @end_dt\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert "WHERE ds BETWEEN @start_dt AND @end_dt" in out

    def test_arbitrary_sqlmesh_at_identifiers_survive_formatting(self):
        sql = (
            "select @EACH(account_id) as account_id from @input_model "
            "where ds = @run_dt and note <> '@run_dt' -- @input_model\n"
        )
        out, warnings = format_sql(sql)
        assert not warnings
        assert "@EACH(account_id) AS account_id" in out
        assert "FROM @input_model" in out
        assert "WHERE ds = @run_dt" in out
        assert "note != '@run_dt' -- @input_model" in out

    def test_inline_jinja_expressions_survive_formatting(self):
        sql = "select {{ dim_col }} as dim from {{ ref('orders') }} where ds = {{ var('ds') }}\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert "{{ dim_col }} AS dim" in out
        assert "FROM {{ ref('orders') }}" in out
        assert "WHERE ds = {{ var('ds') }}" in out

    def test_whole_jinja_control_block_stays_opaque(self):
        block = "{% if is_incremental() %}\nselect bad,unformatted from raw\n{% endif %}\n"
        sql = "select 1 as a\n" + block + "select 2 as b\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert block in out
        assert "SELECT\n   1 AS a\n;\n" in out
        assert "SELECT\n   2 AS b\n;\n" in out

    def test_sqlmesh_formatting_is_idempotent(self):
        sql = (
            "MODEL (\n  name foo.bar,\n  kind FULL\n);\n\n"
            "select {{ dim_col }} as dim from {{ ref('orders') }} "
            "where ds between @start_dt and @end_dt\n"
        )
        out, warnings = format_sql(sql)
        out2, warnings2 = format_sql(out)
        assert not warnings
        assert not warnings2
        assert out == out2

    def test_macro_statement_kept_as_written(self):
        sql = "MODEL (name foo.bar);\n\n-- note\n@DEF(x,   1);\n\n\nselect @x as a\n"
        out, warnings = format_sql(sql)
        assert not warnings
        assert out == "MODEL (name foo.bar);\n\n-- note\n@DEF(x,   1);\n\n\nSELECT\n   @x AS a\n;\n"

    def test_macro_statement_sharing_a_line_with_sql_is_formatted(self):
        sql = "MODEL (name foo.bar);\n@DEF(x, 1); select @x as a\n"
        out, warnings = format_sql(sql)
        out2, _ = format_sql(out)
        assert not warnings
        assert out == "MODEL (name foo.bar);\n@DEF(x, 1)\n;\n\nSELECT\n   @x AS a\n;\n"
        assert out2 == out


class TestCommentsInOneLineConstructs:
    """A -- comment must never swallow SQL that a one-line layout puts after it."""

    def test_commented_window_order_by_breaks_into_clauses(self):
        sql = (
            "SELECT ROW_NUMBER() OVER (PARTITION BY userId, customFieldId\n"
            "  ORDER BY id DESC -- latest record first\n) AS rev_seq FROM t\n"
        )
        result, _ = format_sql(sql)
        expected = "\n".join(
            [
                "   ROW_NUMBER() OVER (",
                "     PARTITION BY",
                "        userId",
                "       ,customFieldId",
                "     ORDER BY",
                "        id DESC -- latest record first",
                "   ) AS rev_seq",
            ]
        )
        assert expected in result

    def test_commented_partition_key_and_frame_keep_comments_at_line_end(self):
        sql = (
            "SELECT SUM(x) OVER (PARTITION BY a -- by a\n"
            "  ORDER BY b ROWS BETWEEN 1 PRECEDING AND CURRENT ROW -- pair\n) AS s FROM t\n"
        )
        result, _ = format_sql(sql)
        assert "     PARTITION BY\n        a -- by a\n     ORDER BY\n        b\n" in result
        assert "     ROWS BETWEEN 1 PRECEDING AND CURRENT ROW -- pair\n   ) AS s" in result

    def test_comment_before_window_order_by_stays_on_its_own_line(self):
        sql = "SELECT SUM(x) OVER (PARTITION BY a\n  -- newest first\n  ORDER BY b DESC) AS s FROM t\n"
        result, _ = format_sql(sql)
        assert "        a\n     -- newest first\n     ORDER BY\n        b DESC\n" in result

    def test_uncommented_window_stays_inline(self):
        result, _ = format_sql("SELECT SUM(x) OVER (PARTITION BY a ORDER BY b) AS s FROM t")
        assert "SUM(x) OVER (PARTITION BY a ORDER BY b) AS s" in result

    def test_commented_argument_wraps_the_call(self):
        result, _ = format_sql("SELECT foo(a /* first */, b) AS c FROM t")
        assert "   foo(\n     a -- first\n    ,b\n  ) AS c" in result

    def test_last_argument_comment_does_not_swallow_the_paren(self):
        result, _ = format_sql("SELECT bar(a, b -- last\n) AS c FROM t")
        assert "    ,b -- last\n  ) AS c" in result

    def test_aggregate_order_by_comment_gets_its_own_line(self):
        sql = "SELECT list(a ORDER BY b -- oldest\n) AS l, string_agg(a, ',' ORDER BY b -- abc\n) AS s FROM t"
        result, _ = format_sql(sql)
        assert "   list(\n     a ORDER BY b -- oldest\n  ) AS l" in result
        assert "  ,STRING_AGG(\n     a, ',' ORDER BY b -- abc\n  ) AS s" in result

    def test_commented_in_list_wraps(self):
        result, _ = format_sql("SELECT a FROM t WHERE a IN (1 -- one\n, 2 -- two\n)")
        assert "WHERE a IN (\n   1 -- one\n  ,2 -- two\n)" in result

    def test_uncommented_call_and_in_list_stay_inline(self):
        result, _ = format_sql("SELECT foo(a, b) AS c FROM t WHERE a IN (1, 2)")
        assert "foo(a, b) AS c" in result
        assert "WHERE a IN (1, 2)" in result

    def test_comment_inside_binary_expression_becomes_block_comment(self):
        result, _ = format_sql("SELECT a /* note */ + 1 AS c, longer_name AS d FROM t")
        # The block comment's width counts toward AS alignment.
        assert "   a /* note */ + 1 AS c\n  ,longer_name      AS d" in result

    def test_comment_before_alias_cast_or_direction_becomes_block_comment(self):
        sql = "SELECT a + 1 -- sum\n AS d, a -- cast\n::int AS e FROM t ORDER BY a -- dir\n DESC"
        result, _ = format_sql(sql)
        assert "   a + 1 /* sum */   AS d\n  ,a /* cast */::int AS e\n" in result
        assert "   a /* dir */ DESC\n" in result
        assert "--" not in result

    def test_comment_followed_only_by_comments_is_not_converted(self):
        result, _ = format_sql("SELECT\n   a -- first\n   -- second\nFROM t")
        assert "/*" not in result

    def test_block_comment_output_is_idempotent(self):
        once, _ = format_sql("SELECT a /* note */ + 1 AS c FROM t")
        twice, _ = format_sql(once)
        assert once == twice
