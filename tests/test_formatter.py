"""Tests for the SQL formatter."""

import pytest

from jarify.config import JarifyConfig
from jarify.formatter import format_sql


def _alias_positions(sql: str, *aliases: str) -> list[int]:
    return [line.index(" AS ") for line in sql.splitlines() if any(f" AS {alias}" in line for alias in aliases)]


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


# Each context from #359 with its column aliases. Their lists start at different
# indents, but min-column-alias names one visible column for all of them.
_NESTED_ALIAS_CONTEXTS = [
    pytest.param(
        "WITH _a AS (SELECT x AS a, y AS b FROM t) SELECT a AS c, b AS d FROM _a",
        ("a", "b", "c", "d"),
        id="main-query",
    ),
    pytest.param(
        "WITH _a AS (SELECT * REPLACE (0 AS x, 'a' AS y) FROM t) SELECT x AS c, y AS d FROM _a",
        ("x", "y", "c", "d"),
        id="replace-list-in-cte",
    ),
    pytest.param(
        "SELECT a AS c, (SELECT max(x) AS m, min(x) AS n FROM u) AS s FROM t",
        ("c", "m", "n", "s"),
        id="scalar-subquery",
    ),
    pytest.param(
        "SELECT a AS c, b AS d FROM t JOIN (SELECT id AS i, v AS w FROM u) s ON s.i = t.id",
        ("c", "d", "i", "w"),
        id="bare-join-subquery",
    ),
    pytest.param(
        "CREATE OR REPLACE MACRO m(p) AS TABLE "
        "(WITH _a AS (SELECT x AS a, y AS b FROM t) SELECT a AS c, b AS d FROM _a)",
        ("a", "b", "c", "d"),
        id="macro-body",
    ),
    pytest.param(
        "WITH _a AS (SELECT 1 AS x), _p AS (WITH _c AS (SELECT user_id, strptime(h, '%Y')::date AS hired_on FROM t) "
        "FROM _c) SELECT x AS e, x AS f FROM _a",
        ("x", "hired_on", "e", "f"),
        id="nested-with-in-from-first-cte",
    ),
    pytest.param(
        "WITH _a AS (SELECT x AS a, y AS b FROM t) SELECT a AS c, b AS d FROM _a UNION ALL SELECT a, b FROM _a",
        ("a", "b", "c", "d"),
        id="union-main-query",
    ),
]


@pytest.mark.parametrize("sql,aliases", _NESTED_ALIAS_CONTEXTS)
@pytest.mark.parametrize("interval", [None, 12])
def test_min_column_alias_is_the_same_visible_column_in_every_context(sql, aliases, interval):
    # min-column-alias = 34 pads text through column 34, so AS starts in column 36,
    # which is also on the column-12 visual guide.
    config = JarifyConfig(min_column_alias=34, alias_visual_guide_interval=interval)
    result, _ = format_sql(sql, config)

    assert _as_columns(result, *aliases) == [36] * len(aliases)
    assert format_sql(result, config)[0] == result


def test_measuring_alias_columns_keeps_generated_table_alias_names():
    # Jarify renders a statement more than once to measure where its alias lists start;
    # those renders mustn't use up the generated names for unnamed table aliases.
    result, _ = format_sql("SELECT a AS x, b AS y FROM (VALUES (1, 2)) AS (a, b)")

    assert "AS _t0(a, b)" in result


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


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        ("bool_or(x IN ('a'))", "BOOL_OR(x IN ('a'))"),
        ("bool_and(x > 1)", "BOOL_AND(x > 1)"),
        ("bool_or(flag)", "BOOL_OR(flag)"),
        ("logical_and(flag)", "BOOL_AND(flag)"),
        ("bool_or(flag::boolean)", "BOOL_OR(flag::boolean)"),
    ],
)
def test_bool_aggregates_keep_their_argument_as_written(call, expected):
    """sqlglot's DuckDB generator casts BOOL_OR and BOOL_AND arguments to BOOLEAN."""
    result, _ = format_sql(f"SELECT {call} AS v FROM t")
    assert f"   {expected} AS v\n" in result


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


def test_several_comments_on_one_node_stay_on_its_line():
    # On lines of their own, the comments after the first would belong to the
    # next token on the next pass: a `)`, `]` or `}`, a clause keyword, `::`.
    sql = "SELECT a /* first */ /* second */ AS c, b FROM t GROUP BY a /* g1 */ /* g2 */;\n"
    result, _ = format_sql(sql)
    assert "   a AS c /* first */ -- second\n  ,b\n" in result
    assert "   a /* g1 */ -- g2\n;" in result
    assert not _lines_continuing_after_line_comment(result)
    assert format_sql(result)[0] == result


def test_several_comments_on_a_cte_go_above_it_one_per_line():
    sql = "WITH _a AS (SELECT 1 AS x)\n/* one */\n/* two */\n,_b AS (SELECT 2 AS y)\nSELECT x, y FROM _a, _b\n"
    result, _ = format_sql(sql)
    assert ")\n-- one\n-- two\n,_b AS\n(" in result
    assert format_sql(result)[0] == result


@pytest.mark.parametrize(
    "head",
    ["_a AS\n-- note\n", "_a AS /* note */ ", "_a AS MATERIALIZED\n-- note\n", "_a (x) AS\n-- note\n"],
)
def test_comment_before_cte_paren_goes_after_as(head):
    """sqlglot drops a comment between a CTE's AS and its "(" (#355)."""
    result, _ = format_sql(f"WITH {head}(SELECT 1 AS x)\nSELECT x FROM _a\n")
    assert result.count("note") == 1
    assert "AS -- note\n(\n" in result or "MATERIALIZED -- note\n(\n" in result
    assert format_sql(result)[0] == result


def test_comment_before_cte_paren_stays_after_as_below_a_comment_above_the_cte():
    sql = "WITH _a AS (SELECT 1 AS x)\n/* block */\n,_b AS\n-- note\n(SELECT 2 AS y)\nSELECT y FROM _b\n"
    result, _ = format_sql(sql)
    assert ")\n-- block\n,_b AS -- note\n(" in result
    assert format_sql(result)[0] == result


def test_comment_before_cte_paren_comes_last_when_comments_go_above():
    sql = "WITH _a AS (SELECT 1 AS x)\n,_b AS -- block\n-- note\n(SELECT 2 AS y)\nSELECT y FROM _b\n"
    result, _ = format_sql(sql)
    assert ")\n-- block\n-- note\n,_b AS\n(" in result
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


class TestCteBodyEndComments:
    """A comment on its own line at the end of a CTE body stays there (#361).

    Regression: the ``)`` closing the body owns the comment, and the CTE wrote
    it above itself, which for the first CTE is the top of the statement.
    """

    def test_comment_after_the_last_clause_stays_in_the_body(self):
        sql = (
            "WITH _tf AS\n(\n  FROM time_frames\n"
            "  WHERE time_frame_key IN ('current_month', 'trailing_12_months') -- only where ends_on >= today\n"
            "  -- because we only keep track of last_visit_at\n)\n"
            "SELECT 1 AS x FROM _tf\n;\n"
        )
        result, _ = format_sql(sql)
        assert result.startswith(
            "WITH _tf AS\n(\n  FROM time_frames\n"
            "  WHERE time_frame_key IN ('current_month', 'trailing_12_months') -- only where ends_on >= today\n"
            "  -- because we only keep track of last_visit_at\n)\nSELECT\n"
        )
        assert format_sql(result)[0] == result

    def test_comment_after_the_last_column_stays_in_the_body(self):
        result, _ = format_sql("WITH _a AS (SELECT 1 AS a, 2 AS b\n  -- c comes later\n)\nSELECT a FROM _a")
        assert "\n    ,2 AS b\n  -- c comes later\n)\nSELECT\n" in result
        assert format_sql(result)[0] == result

    def test_comment_at_the_end_of_a_cte_stays_out_of_the_next_one(self):
        sql = (
            "WITH _a AS (SELECT 1 AS x\n  -- end of _a\n)"
            ", _b AS (SELECT 2 AS y\n  -- end of _b\n)\n"
            "SELECT x, y FROM _a, _b"
        )
        result, _ = format_sql(sql)
        assert "     1 AS x\n  -- end of _a\n)\n,_b AS\n(" in result
        assert "     2 AS y\n  -- end of _b\n)\nSELECT\n" in result
        assert format_sql(result)[0] == result

    @pytest.mark.parametrize("rest", ["", ", _b AS (SELECT 2 AS y)"])
    def test_comment_after_as_does_not_move_the_end_comment(self, rest):
        sql = f"WITH _a AS -- after AS\n(SELECT 1 AS x\n  -- end of _a\n){rest}\nSELECT x FROM _a"
        result, _ = format_sql(sql)
        assert result.startswith("WITH _a AS -- after AS\n(\n  SELECT\n     1 AS x\n  -- end of _a\n)\n")
        assert format_sql(result)[0] == result

    def test_block_comment_stays_in_the_body(self):
        result, _ = format_sql("WITH _a AS (SELECT x FROM t\n  /* WHERE x > 0\n  AND y > 0 */\n)\nSELECT x FROM _a")
        assert "  FROM t\n  /* WHERE x > 0\n  AND y > 0 */\n)\nSELECT\n" in result
        assert format_sql(result)[0] == result

    def test_pivot_order_by_keeps_the_end_comment_in_the_body(self):
        sql = "WITH _d AS (SELECT a, grp, val FROM t\n  -- end of _d\n)\nPIVOT _d ON grp USING first(val) ORDER BY a"
        result, warnings = format_sql(sql)
        assert not warnings
        assert "  FROM t\n  -- end of _d\n)\nPIVOT _d\n" in result

    def test_only_comments_before_a_closing_paren_are_found(self):
        from jarify.formatter import _find_closing_paren_comment_texts

        sql = "WITH _a AS (SELECT 1 -- trailing\n  -- own line\n  /* block */\n) -- after\nSELECT 1"
        assert _find_closing_paren_comment_texts(sql) == {"own line", "block"}


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
        assert "   a\n  /* testing\n  ,b\n  */\n  ,d\n" in result
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


class TestOwnLineBlockComments:
    """A block comment on its own line keeps a line of its own, like a ``--`` comment (#362).

    Regression: between SELECT columns it was pulled onto the end of the
    previous column's line.
    """

    def test_block_comment_between_columns_stays_on_its_own_line(self):
        sql = "SELECT\n   a\n  ,b\n  /* ,c\n  ,d */\n  ,e\nFROM t\n;\n"
        result, _ = format_sql(sql)
        assert result == sql
        assert format_sql(result)[0] == result

    def test_one_line_block_comment_between_columns_gets_its_own_line(self):
        result, _ = format_sql("SELECT\n   a\n  /* note */\n  ,b\nFROM t\n")
        assert "   a\n  -- note\n  ,b\n" in result

    def test_block_comment_before_the_first_column_stays_above_it(self):
        result, _ = format_sql("SELECT\n  /* several\n  lines */\n   a\n  ,b\nFROM t\n")
        assert "SELECT\n   /* several\n  lines */\n   a\n  ,b\n" in result
        assert format_sql(result)[0] == result

    def test_block_comment_after_a_column_stays_on_its_line(self):
        result, _ = format_sql("SELECT\n   a /* first */\n  ,b /* spans\n  lines */\n  ,c\nFROM t\n")
        assert "   a -- first\n  ,b /* spans\n  lines */\n  ,c\n" in result

    def test_block_comment_above_a_cte_stays_above_it(self):
        sql = "WITH _a AS (SELECT 1 AS x)\n/* about _b */\n,_b AS (SELECT 2 AS y)\nSELECT x, y FROM _a, _b\n"
        result, _ = format_sql(sql)
        assert ")\n-- about _b\n,_b AS\n(" in result

    def test_same_block_comment_on_its_own_line_and_after_sql_keeps_the_inline_placement(self):
        # Comments are matched by text, so the two can't be placed differently;
        # the one after `,e` must not move to the line above it.
        comment = "/* ,b\n  ,c */"
        sql = f"SELECT\n   a\n  ,e\n  {comment}\nFROM t\n;\n\nSELECT\n   a\n  ,e {comment}\nFROM t\n;\n"
        result, _ = format_sql(sql)
        assert f"  ,e {comment}\nFROM t\n" in result
        assert format_sql(result)[0] == result

    def test_comment_written_in_two_places_is_not_duplicated(self):
        sql = "SELECT\n   a\n  ,b\n  -- x\n  ,e\nFROM t\n;\n\nSELECT\n   a\n  ,b\n  -- x\nFROM t\n;\n"
        result, _ = format_sql(sql)
        assert result.count("-- x") == 2
        assert "  ,b\n  -- x\n  ,e\n" in result
        assert format_sql(result)[0] == result

    def test_own_line_block_comments_are_found(self):
        from jarify.formatter import _find_leading_comment_texts, _find_trailing_sep_comment_texts

        sql = "SELECT\n  /* lead */\n   a /* trailing */\n  /* sep\n  lines */\n  ,b\n  /* inline */ ,c\nFROM t"
        assert _find_leading_comment_texts(sql) == {"lead"}
        assert _find_trailing_sep_comment_texts(sql) == {"sep\n  lines"}


class TestOwnLineCommentAboveCommentedColumn:
    """A comment on its own line above a column stays there, whatever the column holds (#389).

    sqlglot attaches it to the node the column starts with. An alias with a
    comment of its own doesn't take it over, so it was written inside the
    column, ``a /* above */ AS v -- after``, or lost.
    """

    @pytest.mark.parametrize("comment", ["-- above", "/* above */"])
    def test_comment_above_a_commented_column_stays_above_it(self, comment):
        out, _ = format_sql(f"SELECT\n  {comment}\n  a AS v -- after\n ,b FROM t")
        assert out == "SELECT\n   -- above\n   a AS v -- after\n  ,b\nFROM t\n;\n"
        assert format_sql(out)[0] == out

    def test_comment_above_a_commented_column_in_a_cte_body(self):
        out, _ = format_sql("WITH c AS (SELECT\n  -- above\n  a AS v -- after\n ,b FROM t) SELECT v, b FROM c")
        assert "\n  SELECT\n     -- above\n     a AS v -- after\n    ,b\n  FROM t\n" in out
        assert format_sql(out)[0] == out

    @pytest.mark.parametrize("comment", ["-- above", "/* above */"])
    @pytest.mark.parametrize("after", [" -- after", ""])
    def test_comment_above_a_later_column_lines_up_with_the_commas(self, comment, after):
        # There it follows the column before, which writes it in the same place
        # on the next pass.
        out, _ = format_sql(f"SELECT\n  x,\n  {comment}\n  a AS v{after}\nFROM t")
        assert out == f"SELECT\n   x\n  -- above\n  ,a AS v{after}\nFROM t\n;\n"
        assert format_sql(out)[0] == out

    @pytest.mark.parametrize("before", ["", "x,\n  "])
    def test_single_branch_case_column_with_a_comment_above_becomes_if(self, before):
        # The comment is the column's, so the CASE is rewritten whether or not
        # the alias has a comment of its own, and on every pass.
        out, _ = format_sql(f"SELECT\n  {before}-- above\n  CASE WHEN a THEN 1 ELSE 0 END AS v -- after\nFROM t")
        assert "-- above\n  " in out
        assert "if(a, 1, 0) AS v -- after\n" in out
        assert format_sql(out)[0] == out

    @pytest.mark.parametrize(
        "column",
        [
            "a + 1",
            "a || 'x'",
            "a::int",
            "TRY_CAST(a AS int)",
            "t.a",
            "NOT a",
            "a IN (1, 2)",
            "a IS NOT NULL",
            "SUM(a) OVER (PARTITION BY b)",
            "CASE WHEN a THEN 1 WHEN b THEN 2 END",
            "(a + 1) * 2",
            "coalesce(a, 0)",
        ],
    )
    def test_whatever_the_column_starts_with(self, column):
        out, _ = format_sql(f"SELECT\n  -- above\n  {column} AS v -- after\n ,b FROM t")
        assert out.startswith("SELECT\n   -- above\n   ")
        assert out.count("above") == 1
        assert " AS v -- after\n  ,b\n" in out
        assert format_sql(out)[0] == out

    def test_comment_above_does_not_move_the_as(self):
        out, _ = format_sql("SELECT\n  -- above\n  a AS v -- after\n ,bbbbbbbb AS w FROM t")
        assert "   -- above\n   a        AS v -- after\n  ,bbbbbbbb AS w\n" in out

    def test_comment_above_a_column_without_an_alias(self):
        out, _ = format_sql("SELECT\n  -- above\n  a + 1 -- after\n ,b FROM t")
        assert out == "SELECT\n   -- above\n   a + 1 -- after\n  ,b\nFROM t\n;\n"

    def test_comment_above_a_group_by_or_order_by_key(self):
        sql = (
            "SELECT a + 1, b, count(*) AS n FROM t\n"
            "GROUP BY\n  -- above a key\n  a + 1 -- after the key\n ,b\n"
            "ORDER BY\n  -- above an order key\n  b DESC -- after the order key\n"
        )
        out, _ = format_sql(sql)
        assert "GROUP BY\n   -- above a key\n   a + 1 -- after the key\n  ,b\n" in out
        assert "ORDER BY\n   -- above an order key\n   b DESC -- after the order key\n" in out

    def test_comment_above_a_replace_item(self):
        out, _ = format_sql("SELECT * REPLACE (\n  -- above\n  a + 1 AS a -- after\n) FROM t")
        assert "   REPLACE (\n      -- above\n      a + 1 AS a -- after\n   )\n" in out


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


class TestFirstConditionComments:
    """An own-line comment before a condition stays on its own line (#354)."""

    def test_comment_before_first_where_condition_goes_above_where(self):
        sql = "SELECT a FROM t\nWHERE\n  -- only active rows\n  a = 1\n  AND b = 2\n"
        result, _ = format_sql(sql)
        assert result == "SELECT\n   a\nFROM t\n-- only active rows\nWHERE a = 1\n  AND b = 2\n;\n"
        assert format_sql(result)[0] == result

    def test_comment_before_single_where_condition_goes_above_where(self):
        result, _ = format_sql("SELECT a FROM t\nWHERE\n  -- only active rows\n  a = 1\n")
        assert "FROM t\n-- only active rows\nWHERE a = 1\n;" in result

    def test_comment_goes_where_a_comment_on_the_where_line_goes(self):
        before, _ = format_sql("SELECT a FROM t\nWHERE\n  -- note\n  a = 1 OR b = 2\n")
        on_line, _ = format_sql("SELECT a FROM t\nWHERE -- note\n  a = 1 OR b = 2\n")
        assert before == on_line

    def test_comment_before_first_having_condition_goes_above_having(self):
        sql = "SELECT a, COUNT(*) AS n FROM t GROUP BY ALL\nHAVING\n  -- big\n  COUNT(*) > 1\n  OR a IS NULL\n"
        result, _ = format_sql(sql)
        assert "GROUP BY ALL\n-- big\nHAVING COUNT(*) > 1 OR a IS NULL\n;" in result

    def test_comment_before_first_qualify_condition_stays_below_qualify(self):
        sql = "SELECT a FROM t\nQUALIFY\n  -- latest\n  ROW_NUMBER() OVER (ORDER BY b) = 1\n"
        result, _ = format_sql(sql)
        assert "QUALIFY\n  -- latest\n  ROW_NUMBER() OVER (ORDER BY b) = 1\n;" in result

    def test_comment_before_first_join_on_condition_goes_above_join(self):
        sql = "SELECT a FROM t\nINNER JOIN u ON\n  -- match\n  u.id = t.id\n  AND u.k = 1\n"
        result, _ = format_sql(sql)
        assert "FROM t\n-- match\nINNER JOIN u ON u.id = t.id AND u.k = 1\n;" in result

    @pytest.mark.parametrize(
        "condition",
        ["CAST(a AS int) = 1", "a::int = 1", "a IS NOT NULL", "a IN (1, 2)", "a BETWEEN 1 AND 2", "EXISTS (SELECT 1)"],
    )
    def test_comment_before_any_first_condition_leaves_it_whole(self, condition):
        result, _ = format_sql(f"SELECT a FROM t\nWHERE\n  -- note\n  {condition}\n")
        assert "FROM t\n-- note\nWHERE " in result
        assert "/*" not in result

    def test_comment_after_connector_on_its_own_line_moves_above_it(self):
        sql = "SELECT a FROM t\nWHERE a > 1 AND\n  -- why b\n  b > 2 OR\n  -- why c\n  c = 3\n"
        result, _ = format_sql(sql)
        assert "WHERE a > 1\n  -- why b\n  AND b > 2\n   -- why c\n   OR c = 3\n;" in result

    def test_comment_before_first_branch_in_parens_stays_after_the_paren(self):
        sql = "SELECT a FROM t\nWHERE a > 1 AND (\n  -- either\n  b = 1 OR c = 2)\n"
        result, _ = format_sql(sql)
        assert "  AND (\n    -- either\n    b = 1\n    OR c = 2\n  )\n" in result

    def test_comment_survives_a_query_rendered_twice_for_alias_alignment(self):
        sql = "SELECT (SELECT MAX(x) FROM u WHERE\n  -- latest\n  u.id = t.id) AS m, b AS c FROM t\n"
        result, _ = format_sql(sql)
        assert result.count("-- latest") == 1
        assert "    -- latest\n    WHERE u.id = t.id\n" in result

    @pytest.mark.parametrize(
        "sql",
        [
            # FILTER (WHERE …) stays on the aggregate's line, so the comment can't go above it.
            "SELECT ANY_VALUE(a) FILTER (WHERE\n  -- note\n  b = 1) AS x, c AS y FROM t\n",
            # sqlglot moves a SELECT item's own comments onto its alias when it parses the output.
            "SELECT a AND\n  -- note\n  b AS x, y AS z FROM t\n",
        ],
    )
    def test_comment_that_cannot_move_stays_put_and_stable(self, sql):
        result, _ = format_sql(sql)
        assert result.count("note") == 1
        assert "FILTER(-- note" not in result
        assert format_sql(result)[0] == result


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


class TestFromFirstComments:
    """A comment above a FROM-first query stays above it (#353).

    Regression: the comment was deleted, and after a WITH clause a comment
    above ``SELECT * FROM x`` was written twice.
    """

    def test_comment_above_first_statement_is_kept(self):
        result, _ = format_sql("-- note about this query\nFROM t")
        assert result == "-- note about this query\nFROM t\n;\n"
        assert format_sql(result)[0] == result

    def test_comment_above_later_statement_is_kept(self):
        result, _ = format_sql("SELECT 1 AS x\n;\n\n-- note about the second query\nFROM t")
        assert result.endswith(";\n\n-- note about the second query\nFROM t\n;\n")
        assert format_sql(result)[0] == result

    def test_comment_after_with_clause_is_kept_once(self):
        expected = "WITH _x AS\n(\n  SELECT\n     1 AS a\n)\n-- note\nFROM _x\n;\n"
        for main_query in ("FROM x", "SELECT * FROM x"):
            result, _ = format_sql(f"WITH x AS (SELECT 1 AS a)\n-- note\n{main_query}")
            assert result == expected
            assert format_sql(result)[0] == result

    def test_comment_above_from_first_query_with_select_list_stays_above_it(self):
        result, _ = format_sql("-- note\nFROM t SELECT a")
        assert result == "-- note\nSELECT\n   a\nFROM t\n;\n"

    def test_comment_above_from_first_subquery_is_kept(self):
        result, _ = format_sql("SELECT * FROM (\n-- note\nFROM t) AS s")
        assert result == "FROM (\n  -- note\n  FROM t\n) AS s\n;\n"
        assert format_sql(result)[0] == result


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


class TestWindowListWrapping:
    KEYS = (
        "time_frame_key, client_name, process_type, process_sub_type, audience, "
        "nom_detail_status_keys, nom_status_key, nom_team_status_key, points_actually_awarded"
    )
    WRAPPED_KEYS = (
        "time_frame_key",
        ",client_name",
        ",process_type",
        ",process_sub_type",
        ",audience",
        ",nom_detail_status_keys",
        ",nom_status_key",
        ",nom_team_status_key",
        ",points_actually_awarded",
    )

    def _key_lines(self, column: int) -> list[str]:
        """The wrapped KEYS, with the first key's text starting at *column*."""
        return [" " * (column - 1 if key.startswith(",") else column) + key for key in self.WRAPPED_KEYS]

    def test_long_window_order_by_puts_one_key_per_line(self):
        out, _ = format_sql(f"SELECT ROW_NUMBER() OVER (ORDER BY {self.KEYS}) AS node_id FROM t")
        expected = ["   ROW_NUMBER() OVER (", "     ORDER BY", *self._key_lines(8), "  ) AS node_id"]
        assert "\n".join(expected) in out

    def test_long_partition_by_wraps_while_a_short_order_by_stays_on_its_line(self):
        sql = (
            f"SELECT SUM(x) OVER (PARTITION BY {self.KEYS} ORDER BY created_at "
            "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS s FROM t"
        )
        out, _ = format_sql(sql)
        expected = [
            "     PARTITION BY",
            *self._key_lines(8),
            "     ORDER BY created_at",
            "     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
            "  ) AS s",
        ]
        assert "\n".join(expected) in out

    def test_partition_by_that_fits_stays_on_its_line_in_a_wrapped_window(self):
        sql = (
            "SELECT SUM(a.allocation_per_year / 12) OVER (PARTITION BY a.client_id, a.nomination_application_ids, "
            "a.employee_user_id ORDER BY m.the_month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running "
            "FROM a"
        )
        out, _ = format_sql(sql)
        assert "     PARTITION BY a.client_id, a.nomination_application_ids, a.employee_user_id\n" in out

    def test_long_named_window_puts_one_key_per_line(self):
        out, _ = format_sql(f"SELECT SUM(x) OVER w AS s FROM t WINDOW w AS (PARTITION BY {self.KEYS})")
        assert "\n".join(["WINDOW w AS (", "   PARTITION BY", *self._key_lines(6), ")"]) in out

    def test_long_window_order_by_with_trailing_commas(self):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        out, _ = format_sql(f"SELECT ROW_NUMBER() OVER (ORDER BY {self.KEYS}) AS node_id FROM t", config)
        assert "  ROW_NUMBER() OVER (\n    ORDER BY\n      time_frame_key,\n      client_name,\n" in out

    def test_long_aggregate_order_by_goes_below_the_argument(self):
        out, _ = format_sql(f"SELECT list(node_id ORDER BY {self.KEYS}) AS ids FROM t GROUP BY ALL")
        expected = ["   list(", "     node_id", "     ORDER BY", *self._key_lines(8), "  ) AS ids"]
        assert "\n".join(expected) in out

    def test_wide_aggregate_argument_puts_a_short_order_by_on_its_own_line(self):
        struct = "{'nomination_id': nomination_id, 'created_at': created_at, 'created_on': created_at::date}"
        sql = f"SELECT list({struct} ORDER BY created_at DESC, nomination_id DESC) AS l FROM t GROUP BY ALL"
        out, _ = format_sql(sql)
        assert f"   list(\n     {struct}\n     ORDER BY created_at DESC, nomination_id DESC\n  ) AS l" in out

    def test_short_aggregate_order_by_stays_inline(self):
        out, _ = format_sql("SELECT list(a ORDER BY b, c) AS l FROM t GROUP BY ALL")
        assert "list(a ORDER BY b, c) AS l" in out

    def test_wrapped_window_and_aggregate_lists_are_idempotent(self):
        sql = (
            f"SELECT ROW_NUMBER() OVER (PARTITION BY {self.KEYS} ORDER BY {self.KEYS}) AS n, "
            f"list(x ORDER BY {self.KEYS}) AS l FROM t GROUP BY ALL"
        )
        once, _ = format_sql(sql)
        assert format_sql(once)[0] == once


class TestAggregateOrderByWrapping:
    """An aggregate with arguments before its ORDER BY wraps like list(x ORDER BY …) (#379)."""

    WIDE = (
        "SELECT STRING_AGG(some_long_column_name, ', ' ORDER BY another_long_column_name, "
        "a_third_long_column_name, yet_another_column_name) AS v FROM t GROUP BY ALL"
    )
    KEYS = (
        "nomination_id DESC, created_at DESC, client_id, program_id, nomination_application_id, "
        "employee_user_id, reporting_period_key"
    )
    WRAPPED_KEYS = (
        "nomination_id DESC",
        ",created_at DESC",
        ",client_id",
        ",program_id",
        ",nomination_application_id",
        ",employee_user_id",
        ",reporting_period_key",
    )

    def test_wide_string_agg_puts_order_by_below_the_arguments(self):
        short = "SELECT STRING_AGG(DISTINCT name, ', ' ORDER BY name DESC) AS names FROM t GROUP BY ALL"
        assert "   STRING_AGG(DISTINCT name, ', ' ORDER BY name DESC) AS names\n" in format_sql(short)[0]
        out, _ = format_sql(self.WIDE)
        expected = [
            "   STRING_AGG(",
            "     some_long_column_name",
            "    ,', '",
            "     ORDER BY another_long_column_name, a_third_long_column_name, yet_another_column_name",
            "  ) AS v",
        ]
        assert "\n".join(expected) in out

    def test_long_string_agg_key_list_puts_one_key_per_line(self):
        sql = f"SELECT STRING_AGG(nomination_id, ', ' ORDER BY {self.KEYS}) AS ids FROM t GROUP BY ALL"
        out, _ = format_sql(sql)
        keys = [" " * (7 if key.startswith(",") else 8) + key for key in self.WRAPPED_KEYS]
        expected = ["   STRING_AGG(", "     nomination_id", "    ,', '", "     ORDER BY", *keys, "  ) AS ids"]
        assert "\n".join(expected) in out

    def test_wide_string_agg_with_trailing_commas(self):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        out, _ = format_sql(self.WIDE, config)
        expected = [
            "  STRING_AGG(",
            "    some_long_column_name,",
            "    ', '",
            "    ORDER BY another_long_column_name, a_third_long_column_name, yet_another_column_name",
            "  ) AS v",
        ]
        assert "\n".join(expected) in out

    def test_long_string_agg_key_list_with_trailing_commas(self):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        sql = f"SELECT STRING_AGG(nomination_id, ', ' ORDER BY {self.KEYS}) AS ids FROM t GROUP BY ALL"
        out, _ = format_sql(sql, config)
        assert "    ', '\n    ORDER BY\n      nomination_id DESC,\n      created_at DESC,\n" in out
        assert "\n      reporting_period_key\n  ) AS ids" in out

    def test_other_aggregates_put_order_by_below_their_arguments(self):
        sql = (
            "SELECT arg_max(nomination_application_name, points_awarded ORDER BY created_at DESC, "
            "nomination_application_id, employee_user_id) AS top_name FROM t GROUP BY ALL"
        )
        out, _ = format_sql(sql)
        expected = [
            "   ARG_MAX(",
            "     nomination_application_name",
            "    ,points_awarded",
            "     ORDER BY created_at DESC, nomination_application_id, employee_user_id",
            "  ) AS top_name",
        ]
        assert "\n".join(expected) in out

    def test_wrapped_string_agg_is_idempotent(self):
        sql = f"{self.WIDE[: -len(' FROM t GROUP BY ALL')]}, STRING_AGG(x, ',' ORDER BY {self.KEYS}) AS w FROM t"
        once, _ = format_sql(sql)
        assert "STRING_AGG(\n" in once
        assert format_sql(once)[0] == once


class TestJoinTableComments:
    """A comment on a FROM / JOIN table is kept, after the table or its alias (#355)."""

    def test_comment_after_join_table_is_kept(self):
        out, _ = format_sql("SELECT t.a FROM t INNER JOIN u /* x */ ON u.id = t.id")
        assert out == "SELECT\n   t.a\nFROM t\nINNER JOIN u /* x */ ON u.id = t.id\n;\n"
        assert format_sql(out)[0] == out

    def test_line_comment_after_join_table_does_not_swallow_on(self):
        out, _ = format_sql("SELECT t.a FROM t\nINNER JOIN u -- x\nON u.id = t.id\n")
        assert "INNER JOIN u /* x */ ON u.id = t.id\n" in out

    @pytest.mark.parametrize("join", ["u /* x */ y", "u y /* x */"])
    def test_comment_on_aliased_join_table_follows_the_alias(self, join):
        out, _ = format_sql(f"SELECT x.a FROM t x INNER JOIN {join} ON y.id = x.id")
        assert "INNER JOIN u y /* x */ ON y.id = x.id\n" in out

    def test_comment_between_from_table_and_alias_is_kept(self):
        out, _ = format_sql("SELECT o.a FROM orders /* src */ o")
        assert "FROM orders o -- src\n" in out

    def test_comment_does_not_move_aligned_aliases(self):
        sql = (
            "SELECT o.a FROM orders o LEFT JOIN users /* people */ u ON u.id = o.user_id "
            "LEFT JOIN addresses addr ON addr.id = o.aid"
        )
        out, _ = format_sql(sql)
        assert "FROM orders            o\nLEFT JOIN users        u /* people */ ON" in out
        assert "LEFT JOIN addresses addr ON" in out

    def test_comment_on_join_without_condition_ends_the_line(self):
        out, _ = format_sql("SELECT t.a FROM t CROSS JOIN u /* every row */")
        assert "CROSS JOIN u -- every row\n" in out

    def test_comments_on_table_and_alias_stay_on_the_join_line(self):
        out, _ = format_sql("SELECT x.a FROM t x LEFT JOIN u /* first */ y /* second */ ON y.id = x.id")
        assert "LEFT JOIN u y /* first */ /* second */ ON y.id = x.id\n" in out
        assert format_sql(out)[0] == out


class TestKeywordComments:
    """Comments on keywords whose comments sqlglot drops are kept (#378)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    @pytest.mark.parametrize("comment", ["/* neg */", "-- neg\n "])
    def test_comment_after_not_stays_after_it(self, comment):
        out = self._format(f"SELECT a FROM t WHERE NOT {comment}a")
        assert out == "SELECT\n   a\nFROM t\nWHERE NOT /* neg */ a\n;\n"

    def test_comment_after_not_before_parenthesized_condition(self):
        out = self._format("SELECT a FROM t WHERE b = 1 AND NOT -- neg\n  (c = 1 OR d = 2)")
        assert "WHERE b = 1\n  AND NOT /* neg */ (c = 1 OR d = 2)\n;" in out

    def test_comment_after_not_before_not_in_goes_at_the_end(self):
        out = self._format("SELECT a FROM t WHERE NOT /* c */ a IN (1, 2) AND b = 1")
        assert "WHERE a NOT IN (1, 2) -- c\n  AND b = 1\n;" in out

    def test_comment_above_not_goes_above_the_clause(self):
        out = self._format("SELECT a FROM t WHERE\n  -- why\n  NOT a\n")
        assert "FROM t\n-- why\nWHERE NOT a\n;" in out

    def test_comment_after_not_that_cannot_be_a_block_comment_ends_its_line(self):
        out = self._format("SELECT a FROM t WHERE NOT -- a*/b\n  a")
        assert "WHERE NOT -- a*/b\n" in out

    @pytest.mark.parametrize("qualify", ["QUALIFY /* q */ ", "QUALIFY -- q\n  ", "-- q\nQUALIFY "])
    def test_comment_on_qualify_goes_above_it(self, qualify):
        out = self._format(f"SELECT a FROM t\n{qualify}ROW_NUMBER() OVER (ORDER BY a) = 1")
        assert out == "SELECT\n   a\nFROM t\n-- q\nQUALIFY\n  ROW_NUMBER() OVER (ORDER BY a) = 1\n;\n"

    @pytest.mark.parametrize("join", ["INNER JOIN", "LEFT JOIN"])
    @pytest.mark.parametrize("comment", ["/* on */ ", "-- on\n  "])
    def test_comment_on_join_on_goes_above_the_join(self, join, comment):
        out = self._format(f"SELECT t.a FROM t {join} u ON {comment}u.id = t.id")
        assert out == f"SELECT\n   t.a\nFROM t\n-- on\n{join} u ON u.id = t.id\n;\n"

    def test_comment_above_join_on_goes_above_the_join(self):
        out = self._format("SELECT t.a FROM t INNER JOIN u\n  -- on\n  ON u.id = t.id")
        assert "FROM t\n-- on\nINNER JOIN u ON u.id = t.id\n;" in out

    def test_comment_on_join_using_goes_above_the_join(self):
        out = self._format("SELECT t.a FROM t LEFT JOIN u USING /* by id */ (id)")
        assert "FROM t\n-- by id\nLEFT JOIN u USING (id)\n;" in out

    def test_comment_after_union_all_goes_above_it(self):
        out = self._format("SELECT a FROM t\nUNION ALL -- managers too\nSELECT b FROM u")
        assert "FROM t\n-- managers too\nUNION ALL\nSELECT" in out

    @pytest.mark.parametrize("comment", ["-- c\n  ", "/* c */ "])
    def test_comment_between_if_and_its_alias_is_kept(self, comment):
        out = self._format(f"SELECT if(a = 1, 'x', 'y') {comment}AS v FROM t")
        assert out == "SELECT\n   if(a = 1, 'x', 'y') AS v -- c\nFROM t\n;\n"

    def test_comment_above_if_is_kept(self):
        out = self._format("SELECT\n  -- why\n  if(a = 1, 'x', 'y') AS v\nFROM t")
        assert out == "SELECT\n   -- why\n   if(a = 1, 'x', 'y') AS v\nFROM t\n;\n"

    def test_comment_after_filter_is_kept(self):
        out = self._format("SELECT count(*) FILTER (WHERE a) -- c\n  AS n FROM t")
        assert "COUNT(*) FILTER(WHERE a) AS n -- c\n" in out

    def test_comment_after_then_goes_above_then(self):
        sql = (
            "SELECT CASE WHEN a = 1 THEN /* c */ CASE WHEN b = 1 THEN 1 WHEN b = 2 THEN 2 END "
            "WHEN a = 2 THEN 3 END AS v FROM t"
        )
        out = self._format(sql)
        assert "     WHEN a = 1\n     -- c\n     THEN CASE\n" in out

    def test_comments_above_when_and_else_stay_above_them(self):
        sql = (
            "SELECT\n  CASE\n    -- first\n    WHEN a = 1 THEN 1\n    -- second\n    WHEN a = 2 THEN 2\n"
            "    -- fallback\n    ELSE 3\n  END AS v\nFROM t"
        )
        out = self._format(sql)
        assert out == (
            "SELECT\n   CASE\n     -- first\n     WHEN a = 1\n     THEN 1\n     -- second\n     WHEN a = 2\n"
            "     THEN 2\n     -- fallback\n     ELSE 3\n   END AS v\nFROM t\n;\n"
        )

    def test_comments_after_when_and_else_go_above_them(self):
        out = self._format("SELECT CASE WHEN /* w */ a THEN 1 WHEN b THEN 2 ELSE -- e\n  3 END AS v FROM t")
        assert "   CASE\n     -- w\n     WHEN a\n" in out
        assert "     -- e\n     ELSE 3\n" in out

    def test_comments_in_simple_case_go_above_the_when_line(self):
        out = self._format("SELECT CASE x WHEN /* w */ 1 THEN /* t */ 'a' ELSE /* e */ 'b' END AS v FROM t")
        assert "   CASE x\n    -- w\n    -- t\n    WHEN 1 THEN 'a'\n    -- e\n    ELSE 'b'\n" in out

    def test_comment_in_a_nested_case_goes_above_its_keyword(self):
        sql = "SELECT CASE WHEN a THEN CASE WHEN b THEN /* t */ 1 WHEN c THEN 2 END WHEN d THEN 3 END AS v FROM t"
        out = self._format(sql)
        assert "            WHEN b\n            -- t\n            THEN 1\n" in out

    def test_case_on_one_line_writes_keyword_comments_after_the_keyword(self):
        # A CASE always takes its multi-line form, but its one-line form must
        # keep the comments too, without letting them swallow SQL.
        from jarify.generator import JarifyGenerator
        from jarify.parser import parse_sql

        (tree,) = parse_sql("SELECT CASE WHEN /* w */ a THEN -- t\n 1 ELSE /* e */ 2 END")
        compact = JarifyGenerator(JarifyConfig())._compact_sql(tree.expressions[0])
        assert compact == "CASE WHEN /* w */ a THEN /* t */ 1 ELSE /* e */ 2 END"

    def test_single_when_case_with_a_keyword_comment_stays_case(self):
        out = self._format("SELECT CASE WHEN a THEN /* t */ 1 END AS v FROM t")
        assert "if(" not in out
        assert "     -- t\n     THEN 1\n" in out

    @pytest.mark.parametrize("join", ["", "LEFT JOIN u ON u.a = s.a"])
    def test_comment_before_subquery_closing_paren_ends_its_body(self, join):
        out = self._format(f"SELECT s.a FROM (\n  SELECT a FROM t\n  -- end of body\n) s {join}")
        assert "  FROM t\n  -- end of body\n) AS s\n" in out

    def test_comment_before_closing_paren_of_unaliased_subquery_ends_its_body(self):
        out = self._format("SELECT a FROM (\n  SELECT a FROM t\n  /* end */\n)")
        assert "  FROM t\n  -- end\n)\n;" in out

    def test_comment_before_joined_subquery_closing_paren_ends_its_body(self):
        out = self._format("SELECT t.a FROM t LEFT JOIN (\n  SELECT a FROM u\n  -- end\n) s ON s.a = t.a")
        assert "  FROM u\n  -- end\n) AS s ON s.a = t.a\n" in out

    def test_comment_after_subquery_closing_paren_follows_the_alias(self):
        out = self._format("SELECT s.a FROM (SELECT a FROM t) -- after\n  s")
        assert ") AS s -- after\n" in out


class TestOperatorComments:
    """A comment on a word of an operator stays after that word (#388, #382)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    @pytest.mark.parametrize(
        ("condition", "expected"),
        [
            ("a NOT /* c */ IN (1, 2)", "a NOT /* c */ IN (1, 2)"),
            ("a NOT IN /* c */ (1, 2)", "a NOT IN /* c */ (1, 2)"),
            ("a NOT -- c\n  IN (1, 2)", "a NOT /* c */ IN (1, 2)"),
            ("a NOT IN -- c\n  (1, 2)", "a NOT IN /* c */ (1, 2)"),
            ("a IN /* c */ (1, 2)", "a IN /* c */ (1, 2)"),
            ("a IN /* c */ (SELECT b FROM u)", "a IN /* c */ (SELECT b FROM u)"),
            ("a NOT /* c */ LIKE 'x%'", "a NOT /* c */ LIKE 'x%'"),
            ("a NOT LIKE /* c */ 'x%'", "a NOT LIKE /* c */ 'x%'"),
            ("a ILIKE /* c */ 'x%'", "a ILIKE /* c */ 'x%'"),
            ("a NOT /* c */ GLOB 'x*'", "a NOT /* c */ GLOB 'x*'"),
            ("a NOT SIMILAR TO /* c */ 'x'", "a NOT SIMILAR TO /* c */ 'x'"),
            ("a LIKE 'x!%' ESCAPE /* c */ '!'", "a LIKE 'x!%' ESCAPE /* c */ '!'"),
            ("a NOT /* c */ BETWEEN 1 AND 2", "a NOT /* c */ BETWEEN 1 AND 2"),
            ("a BETWEEN /* c */ 1 AND 2", "a BETWEEN /* c */ 1 AND 2"),
            ("a BETWEEN 1 AND -- c\n  2", "a BETWEEN 1 AND /* c */ 2"),
            ("a IS /* c */ NOT NULL", "a IS /* c */ NOT NULL"),
            ("a IS NOT /* c */ NULL", "a IS NOT /* c */ NULL"),
            ("a IS -- c\n  NULL", "a IS /* c */ NULL"),
            ("a IS NOT /* c */ TRUE", "a IS NOT /* c */ true"),
            ("a IS /* c */ DISTINCT FROM b", "a IS /* c */ DISTINCT FROM b"),
            ("a IS NOT DISTINCT FROM /* c */ b", "a IS NOT DISTINCT FROM /* c */ b"),
        ],
    )
    def test_comment_on_an_operator_word_stays_after_it(self, condition, expected):
        out = self._format(f"SELECT a FROM t WHERE {condition}")
        assert f"WHERE {expected}\n;" in out

    def test_comment_on_an_operator_in_a_select_list(self):
        out = self._format("SELECT a NOT /* c */ IN (1, 2) AS x, b NOT /* d */ LIKE 'y' AS y FROM t")
        assert "   a NOT /* c */ IN (1, 2) AS x\n  ,b NOT /* d */ LIKE 'y'  AS y\n" in out

    def test_comment_on_the_tilde_operator_stays_after_it(self):
        # `~` stays an operator (#396), so its comment stays after it.
        out = self._format("SELECT a FROM t WHERE a ~ /* c */ 'x'")
        assert "WHERE a ~ /* c */ 'x'\n" in out

    @pytest.mark.parametrize(
        "condition", ["a NOT /* c */ IN UNNEST([1, 2])", "a NOT /* c */ BETWEEN SYMMETRIC 1 AND 2"]
    )
    def test_comment_on_an_operator_jarify_rewrites_goes_at_the_end(self, condition):
        out = self._format(f"SELECT a FROM t WHERE {condition}")
        assert out.count("-- c") == 1

    def test_is_not_true_and_false_keep_not_after_is(self):
        out = self._format("SELECT a FROM t WHERE a IS NOT TRUE AND b IS NOT FALSE")
        assert "WHERE a IS NOT true\n  AND b IS NOT false\n;" in out

    def test_not_in_front_of_is_true_moves_after_is(self):
        out = self._format("SELECT NOT a IS TRUE AS x, NOT (b IS FALSE) AS y FROM t")
        assert "   a IS NOT true    AS x\n  ,NOT (b IS false) AS y\n" in out


class TestClauseKeywordComments:
    """Comments on WINDOW, DISTINCT ON, FILTER and OVER are kept (#388)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    @pytest.mark.parametrize("window", ["WINDOW /* c */ w", "WINDOW -- c\n  w", "-- c\nWINDOW w"])
    def test_comment_on_window_goes_above_it(self, window):
        out = self._format(f"SELECT SUM(a) OVER w AS s FROM t\n{window} AS (ORDER BY a)")
        assert "FROM t\n-- c\nWINDOW w AS (ORDER BY a)\n;" in out

    def test_comment_on_a_named_windows_as_goes_after_it(self):
        out = self._format("SELECT SUM(a) OVER w AS s FROM t WINDOW w AS /* c */ (ORDER BY a)")
        assert "WINDOW w AS (ORDER BY a) -- c\n;" in out

    @pytest.mark.parametrize(
        "distinct", ["DISTINCT ON /* c */ (a)", "DISTINCT /* c */ ON (a)", "DISTINCT ON -- c\n (a)"]
    )
    def test_comment_on_distinct_on_stays_after_on(self, distinct):
        out = self._format(f"SELECT {distinct} a, b FROM t")
        assert out.startswith("SELECT DISTINCT ON /* c */ (a)\n   a\n  ,b\n")

    def test_comment_after_distinct_ons_paren_goes_on_its_first_item(self):
        out = self._format("SELECT DISTINCT ON ( -- c\n a) a, b FROM t")
        assert out.startswith("SELECT DISTINCT ON (\n   a -- c\n)\n   a\n  ,b\n")

    @pytest.mark.parametrize(
        "filter_", ["FILTER /* c */ (WHERE a)", "FILTER ( -- c\n  WHERE a)", "FILTER (WHERE /* c */ a)"]
    )
    def test_comment_in_filter_goes_after_where(self, filter_):
        out = self._format(f"SELECT COUNT(*) {filter_} AS n FROM t")
        assert "   COUNT(*) FILTER(WHERE /* c */ a) AS n\n" in out

    @pytest.mark.parametrize(
        "over",
        [
            "FILTER (WHERE a) /* c */ OVER (PARTITION BY b)",
            "FILTER (WHERE a) -- c\n  OVER (PARTITION BY b)",
            "FILTER (WHERE a) OVER /* c */ (PARTITION BY b)",
        ],
    )
    def test_comment_before_a_window_spec_goes_after_the_window(self, over):
        out = self._format(f"SELECT COUNT(*) {over} AS n FROM t")
        assert "   COUNT(*) FILTER(WHERE a) OVER (PARTITION BY b) AS n -- c\n" in out


class TestOpeningBracketComments:
    """A comment after an opening bracket goes on the first item (#388)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    @pytest.mark.parametrize("comment", ["-- c\n  ", "/* c */ "])
    def test_comment_after_a_calls_paren_goes_on_its_first_argument(self, comment):
        out = self._format(f"SELECT coalesce( {comment}a, b, c) AS v FROM t")
        assert "   coalesce(\n     a -- c\n    ,b\n    ,c\n  ) AS v\n" in out

    @pytest.mark.parametrize("call", ["CAST( -- c\n a AS int)", "COUNT( -- c\n *)", "if( -- c\n a, 1, 2)"])
    def test_comment_after_the_paren_of_other_calls_is_kept(self, call):
        out = self._format(f"SELECT {call} AS v FROM t")
        assert "-- c" in out or "/* c */" in out

    def test_comment_after_an_in_lists_paren_goes_on_its_first_value(self):
        out = self._format("SELECT a FROM t WHERE a IN ( -- c\n  1, 2)")
        assert "WHERE a IN (\n   1 -- c\n  ,2\n)\n;" in out

    def test_comment_after_a_list_literals_bracket_goes_on_its_first_item(self):
        out = self._format("SELECT [ -- c\n  1, 2] AS l FROM t")
        assert "   [\n     1 -- c\n    ,2\n  ] AS l\n" in out

    def test_comment_in_the_parens_of_a_call_without_arguments_follows_the_call(self):
        out = self._format("SELECT ROW_NUMBER( /* c */ ) OVER (ORDER BY a) AS rn, b FROM t")
        assert "   ROW_NUMBER() OVER (ORDER BY a) AS rn -- c\n" in out

    @pytest.mark.parametrize("value", ["CAST( /* c */ a + b AS int)", "CAST(a /* c */ + b AS int)"])
    def test_commented_operator_in_a_cast_is_laid_out_as_its_parentheses(self, value):
        out = self._format(f"SELECT {value} AS v, d FROM t")
        assert "   (\n    a /* c */ + b\n  )::int AS v\n" in out

    @pytest.mark.parametrize("literal", ["[1, 2]", "{'a': 1}"])
    def test_comment_above_a_list_or_struct_literal_stays_above_it(self, literal):
        out = self._format(f"SELECT\n  -- c\n  {literal} AS v, d FROM t")
        assert f"SELECT\n   -- c\n   {literal} AS v\n" in out

    def test_comment_on_a_lambda_parameter_column_is_kept(self):
        out = self._format("SELECT list_transform(l, lambda x: x.key /* c */ + 1) AS v FROM t")
        assert "lambda x: x.key /* c */ + 1\n" in out

    @pytest.mark.parametrize("using", ["USING ( -- c\n  id)", "USING (id /* c */)", "USING (id -- c\n)"])
    def test_comment_on_a_using_column_is_kept(self, using):
        out = self._format(f"SELECT a FROM t INNER JOIN u {using}")
        assert "INNER JOIN u USING (id /* c */)\n;" in out


class TestStructComments:
    """Comments in a struct literal are kept (#388)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    @pytest.mark.parametrize("comment", ["-- c\n  ", "/* c */ "])
    def test_comment_between_a_struct_and_its_alias_follows_the_alias(self, comment):
        out = self._format(f"SELECT {{'a': 1}} {comment}AS v FROM t")
        assert "   {'a': 1} AS v -- c\n" in out

    @pytest.mark.parametrize(
        "struct",
        ["{'a': 1, -- c\n 'b': 2}", "{ -- c\n 'a': 1, 'b': 2}", "{'a': /* c */ 1, 'b': 2}", "{a: 1, -- c\n b: 2}"],
    )
    def test_comment_in_a_struct_stays_with_its_entry(self, struct):
        out = self._format(f"SELECT {struct} AS v FROM t")
        assert "   {\n     'a': 1 -- c\n    ,'b': 2\n  } AS v\n" in out

    def test_comment_on_a_struct_key_stays_after_it(self):
        out = self._format("SELECT {'a' /* c */: 1} AS v FROM t")
        assert "     'a' /* c */: 1\n" in out

    def test_commented_out_entries_keep_their_own_lines(self):
        sql = "SELECT {\n  'a': a\n  ,'b': b\n-- ,'c': c\n  ,'d': d\n} AS v FROM t"
        out = self._format(sql)
        assert "   {\n     'a': a\n    ,'b': b\n    -- ,'c': c\n    ,'d': d\n  } AS v\n" in out


class TestValuesComments:
    """Comments on VALUES rows are kept (#388)."""

    @staticmethod
    def _format(sql: str) -> str:
        out, _ = format_sql(sql)
        assert format_sql(out)[0] == out
        return out

    def test_comment_after_a_cte_values_row_stays_after_it(self):
        out = self._format("WITH c (a, b) AS (VALUES (1, 'x'), -- first\n (2, 'y')) SELECT a, b FROM c")
        assert "  VALUES\n     (1, 'x') -- first\n    ,(2, 'y')\n)" in out

    def test_comment_after_the_last_cte_values_row_stays_after_it(self):
        out = self._format("WITH c (a, b) AS (VALUES ('MDG', 'MGA') -- madagascar\n) SELECT a, b FROM c")
        assert "  VALUES\n     ('MDG', 'MGA') -- madagascar\n)" in out

    @pytest.mark.parametrize(
        ("sql", "rows"),
        [
            (
                "WITH c (a) AS (VALUES (1)\n  -- second\n  , (2)) SELECT a FROM c",
                "  VALUES\n     (1)\n    -- second\n    ,(2)\n)",
            ),
            ("INSERT INTO t VALUES (1)\n  -- second\n  , (2)", "VALUES\n   (1)\n  -- second\n  ,(2)\n;"),
            ("INSERT INTO t VALUES\n  -- first\n  (1), (2)", "VALUES\n   -- first\n   (1)\n  ,(2)\n;"),
        ],
    )
    def test_own_line_comment_between_rows_stays_above_the_next_row(self, sql, rows):
        assert rows in self._format(sql)

    @pytest.mark.parametrize("values", ["VALUES -- rows\n (1), (2)", "\n  -- rows\n  VALUES (1), (2)"])
    def test_comment_on_values_goes_after_it(self, values):
        out = self._format(f"WITH c (a) AS ({values}) SELECT a FROM c")
        assert "  VALUES -- rows\n     (1)\n    ,(2)\n)" in out


class TestCommentTextKept:
    """Rewriting ifnull, numeric and reserved-word casts leaves comments and strings alone (#388)."""

    def test_ifnull_in_a_comment_keeps_its_case(self):
        out, _ = format_sql("SELECT ifnull(a, 0) AS v -- uses IFNULL(a, 0) on purpose\nFROM t")
        assert "-- uses IFNULL(a, 0) on purpose\n" in out

    def test_numeric_and_reserved_casts_in_comments_and_strings_are_kept(self):
        sql = "SELECT 'IFNULL', 'NUMERIC', '::filter[]' AS s /* NUMERIC ::filter[] */, a::NUMERIC AS n FROM t"
        out, _ = format_sql(sql)
        assert "   'IFNULL'\n  ,'NUMERIC'\n  ,'::filter[]' AS s -- NUMERIC ::filter[]\n  ,a::numeric   AS n\n" in out


class TestGroupByAllComments:
    """prefer-group-by-all keeps a GROUP BY list that carries a comment (#388)."""

    def test_group_by_with_the_select_lists_comment_is_kept(self):
        sql = "SELECT a, b -- c1\n, SUM(c) AS s FROM t GROUP BY a, b -- c1\n"
        out, _ = format_sql(sql)
        assert out.count("-- c1") == 2
        assert "GROUP BY\n   a\n  ,b -- c1\n;" in out


class TestListOwnLineComments:
    """An own-line comment before a list item lines up with the commas on the first pass (#382)."""

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("SELECT a FROM t WHERE b IN (\n  1,\n  -- note\n  2\n)", "WHERE b IN (\n   1\n  -- note\n  ,2\n)\n;"),
            (
                "SELECT a FROM t WHERE x = 1 AND b IN (\n  1,\n  -- note\n  2\n)",
                "  AND b IN (\n     1\n    -- note\n    ,2\n  )\n;",
            ),
        ],
    )
    def test_own_line_comment_in_an_in_list_lines_up_with_the_commas(self, sql, expected):
        out, _ = format_sql(sql)
        assert expected in out
        assert format_sql(out)[0] == out


class TestCtesInSubqueries:
    """A subquery holding a WITH is laid out with its CTEs as at the top level (#378)."""

    def test_from_subquery_lays_out_its_ctes(self):
        sql = "SELECT s.a FROM (\n  WITH c AS ( -- note c\n    SELECT 1 AS a\n  )\n  SELECT a FROM c\n) s"
        out, _ = format_sql(sql)
        assert out == (
            "SELECT\n   s.a\nFROM (\n  WITH c AS -- note c\n  (\n    SELECT\n       1 AS a\n  )\n"
            "  SELECT\n     a\n  FROM c\n) AS s\n;\n"
        )
        assert format_sql(out)[0] == out

    def test_in_subquery_lays_out_its_ctes(self):
        out, _ = format_sql("SELECT a FROM t WHERE a IN (WITH c AS (SELECT 1 AS a) SELECT a FROM c)")
        assert "WHERE a IN\n(\n  WITH c AS\n  (\n" in out

    def test_cte_comment_survives_a_subquery_rendered_twice(self):
        out, _ = format_sql("SELECT (WITH c AS ( -- note c\n  SELECT 1 AS a) SELECT max(a) FROM c) AS m, 1 AS n")
        assert out.count("-- note c") == 1

    def test_then_value_holding_a_with_takes_its_own_layout(self):
        sql = "SELECT CASE WHEN a THEN (WITH c AS (SELECT 1 AS a) SELECT max(a) FROM c) WHEN b THEN 2 END AS v"
        out, _ = format_sql(sql)
        # The value's other lines keep their column relative to THEN, as a
        # WHEN condition's do relative to WHEN: its ")" goes under THEN.
        assert "     THEN (\n       WITH c AS\n" in out
        assert "       FROM c\n     )\n     WHEN b\n" in out


class TestNestedJoins:
    """A nested join keeps its inner join, written as a parenthesized group (#386)."""

    def test_nested_join_is_kept_in_parentheses(self):
        out, _ = format_sql("SELECT t.a FROM t JOIN u JOIN v ON v.id = u.id ON u.id = t.id")
        assert out == (
            "SELECT\n   t.a\nFROM t\nINNER JOIN (\n  u\n  INNER JOIN v ON v.id = u.id\n) ON u.id = t.id\n;\n"
        )
        assert format_sql(out)[0] == out

    def test_nested_join_with_using_is_kept(self):
        out, _ = format_sql("SELECT t.a FROM t JOIN u JOIN v USING (id) USING (id)")
        assert "INNER JOIN (\n  u\n  INNER JOIN v USING (id)\n) USING (id)\n" in out

    def test_group_aliases_align_like_a_from_clause(self):
        sql = (
            "SELECT tt.a FROM tbl tt LEFT JOIN (users uu JOIN visits vv ON vv.uid = uu.id "
            "LEFT JOIN x.yy_things y ON y.vid = vv.id) ON uu.id = tt.uid"
        )
        out, _ = format_sql(sql)
        assert (
            "LEFT JOIN (\n"
            "  users                uu\n"
            "  INNER JOIN visits    vv ON vv.uid = uu.id\n"
            "  LEFT JOIN x.yy_things y ON y.vid = vv.id\n"
            ") ON uu.id = tt.uid\n"
        ) in out

    @pytest.mark.parametrize(
        ("group", "first_line"),
        [
            ("(\n  -- c1\n  u JOIN v ON v.id = u.id)", "  u -- c1\n"),
            ("(u /* c1 */ x JOIN v y ON y.id = x.id)", "  u            x -- c1\n"),
            ("(u x /* c1 */ JOIN v y ON y.id = x.id)", "  u            x -- c1\n"),
        ],
    )
    def test_first_table_comment_is_written_once(self, group, first_line):
        out, _ = format_sql(f"SELECT t.a FROM t LEFT JOIN {group} ON t.id = t.id")
        assert first_line in out
        assert out.count("c1") == 1
        assert format_sql(out)[0] == out

    def test_deeper_nesting_keeps_every_join(self):
        out, _ = format_sql("SELECT t.a FROM t JOIN u JOIN v JOIN w ON w.id = v.id ON v.id = u.id ON u.id = t.id")
        assert (
            "INNER JOIN (\n"
            "  u\n"
            "  INNER JOIN (\n"
            "    v\n"
            "    INNER JOIN w ON w.id = v.id\n"
            "  ) ON v.id = u.id\n"
            ") ON u.id = t.id\n"
        ) in out
        assert format_sql(out)[0] == out


_WITH_SUBQUERY = "(WITH c AS (SELECT 1 AS a) SELECT max(a) FROM c)"
_WITH_SUBQUERY_POSITIONS = {
    "parenthesized_condition": "SELECT a FROM t WHERE (a IN {q} OR b)",
    "parenthesized_condition_after_and": "SELECT a FROM t WHERE x = 1 AND (a IN {q} OR b)",
    "parenthesized_comparison": "SELECT a FROM t WHERE ({q} > 1)",
    "or_chain": "SELECT a FROM t WHERE a IN {q} OR b",
    "having": "SELECT a, count(*) AS n FROM t GROUP BY a HAVING count(*) > {q} OR a = 1",
    "join_on": "SELECT t.a FROM t INNER JOIN u ON u.id = t.id AND u.a IN {q}",
    "join_on_single_condition": "SELECT t.a FROM t INNER JOIN u ON u.a IN {q}",
    "join_on_parenthesized": "SELECT t.a FROM t INNER JOIN u ON (u.a IN {q} OR u.b)",
    "if_condition": "SELECT if(a IN {q}, 1, 0) AS v FROM t",
    "if_then": "SELECT if(x, {q}, 0) AS v FROM t",
    "if_else": "SELECT if(x, 0, {q}) AS v FROM t",
    "simple_case_when": "SELECT CASE x WHEN {q} THEN 1 WHEN 2 THEN 3 END AS v FROM t",
    "select_list_parentheses": "SELECT (a IN {q} OR b) AS v FROM t",
    "filter_where": "SELECT COUNT(*) FILTER (WHERE a IN {q} OR b) AS n FROM t",
    "cte_body": "WITH d AS (SELECT a FROM t WHERE (a IN {q} OR b)) SELECT a FROM d",
}


class TestCtesInExpressionSubqueries:
    """A subquery holding a WITH is laid out with its CTEs as at the top level in every position (#389).

    Regression: a parenthesized condition, a JOIN condition, an OR chain,
    if()'s arguments and a simple CASE's WHEN value rendered it on one line,
    which broke after ``WITH c AS`` and crammed the rest together.
    """

    @pytest.mark.parametrize("sql", _WITH_SUBQUERY_POSITIONS.values(), ids=_WITH_SUBQUERY_POSITIONS.keys())
    def test_ctes_are_laid_out_as_at_the_top_level(self, sql):
        out, _ = format_sql(sql.format(q=_WITH_SUBQUERY))
        lines = out.splitlines()
        with_rows = [i for i, line in enumerate(lines) if line.lstrip().startswith("WITH c AS")]
        assert len(with_rows) == 1, f"WITH doesn't start a line:\n{out}"
        row = with_rows[0]
        indent = " " * (len(lines[row]) - len(lines[row].lstrip()))
        assert lines[row] == f"{indent}WITH c AS"
        assert lines[row + 1 : row + 4] == [f"{indent}(", f"{indent}  SELECT", f"{indent}     1 AS a"]
        assert format_sql(out)[0] == out

    def test_parenthesized_condition_takes_its_multi_line_form(self):
        out, _ = format_sql("SELECT a FROM t WHERE (a IN (WITH c AS (SELECT 1 AS a) SELECT a FROM c) OR b)")
        assert out == (
            "SELECT\n   a\nFROM t\nWHERE (\n  a IN\n  (\n    WITH c AS\n    (\n      SELECT\n         1 AS a\n    )\n"
            "    SELECT\n       a\n    FROM c\n  )\n  OR b\n)\n;\n"
        )

    def test_if_argument_wraps_the_call(self):
        out, _ = format_sql("SELECT if(x, (WITH c AS (SELECT 1 AS a) SELECT max(a) FROM c), 0) AS v FROM t")
        assert "   if(\n      x\n     ,(\n        WITH c AS\n        (\n" in out
        assert "        FROM c\n      )\n     ,0\n  ) AS v\n" in out

    def test_join_condition_is_laid_out_like_where(self):
        sql = "SELECT t.a FROM t INNER JOIN u ON u.id = t.id AND u.a IN (WITH c AS (SELECT 1 AS a) SELECT a FROM c)"
        out, _ = format_sql(sql)
        assert "INNER JOIN u ON u.id = t.id\n            AND u.a IN\n            (\n              WITH c AS\n" in out

    @pytest.mark.parametrize("when_value", [_WITH_SUBQUERY, "CASE WHEN a THEN 1 WHEN b THEN 2 END"])
    def test_simple_case_branches_after_a_multi_line_when_value_are_not_padded(self, when_value):
        out, _ = format_sql(f"SELECT CASE x WHEN {when_value} THEN 1 WHEN 2 THEN 3 END AS v FROM t")
        assert "\n    WHEN 2 THEN 3\n" in out


class TestTildeOperator:
    """`~` and `!~` stay operators instead of becoming regexp_full_match() (#396)."""

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("SELECT a FROM t WHERE a ~ 'b'", "WHERE a ~ 'b'\n"),
            ("SELECT a FROM t WHERE a !~ 'b'", "WHERE a !~ 'b'\n"),
            ("SELECT a FROM t WHERE NOT (a ~ 'b')", "WHERE NOT (a ~ 'b')\n"),
            ("SELECT regexp_full_match(a, 'b') AS m FROM t", "   regexp_full_match(a, 'b') AS m\n"),
            ("SELECT a FROM t WHERE a ~ /* c */ 'b'", "WHERE a ~ /* c */ 'b'\n"),
        ],
    )
    def test_operator_is_kept(self, sql, expected):
        out, _ = format_sql(sql)
        assert expected in out
        assert format_sql(out)[0] == out


class TestValuesTableColumns:
    """A VALUES table keeps the column names its alias gives (#396)."""

    def test_short_values_table_stays_on_one_line(self):
        out, _ = format_sql("SELECT * FROM (VALUES (1, 'a'), (2, 'b')) v(id, name)")
        assert out == "FROM (VALUES (1, 'a'), (2, 'b')) AS v(id, name)\n;\n"

    def test_long_values_table_is_laid_out_like_a_subquery(self):
        rows = ", ".join(f"({i}, 'a fairly long label number {i}')" for i in range(4))
        out, _ = format_sql(f"SELECT v.id FROM (VALUES {rows}) v(id, name)")
        assert "FROM (\n  VALUES\n     (0, 'a fairly long label number 0')\n    ,(1, " in out
        assert "\n) AS v(id, name)\n" in out
        assert format_sql(out)[0] == out

    def test_values_without_column_names_still_becomes_values(self):
        out, _ = format_sql("SELECT * FROM (VALUES (1, 'a')) v")
        assert out == "VALUES\n   (1, 'a')\n;\n"


class TestColumnNameLists:
    """An INSERT's or a view's column-name list stays valid SQL (#396)."""

    def test_short_insert_column_list_stays_on_the_line(self):
        out, _ = format_sql("INSERT INTO t (a, b) VALUES (1, 2)")
        assert out.startswith("INSERT INTO t (a, b)\nVALUES\n")

    def test_long_insert_column_list_puts_one_name_per_line(self):
        cols = ", ".join(f"some_rather_long_column_name_{i}" for i in range(6))
        out, _ = format_sql(f"INSERT INTO t ({cols}) SELECT * FROM u")
        assert "INSERT INTO t\n(\n   some_rather_long_column_name_0\n  ,some_rather_long_column_name_1\n" in out
        assert format_sql(out)[0] == out

    def test_commented_column_name_keeps_its_comment(self):
        out, _ = format_sql("INSERT INTO t (a, -- first\n b) VALUES (1, 2)")
        assert "(\n   a -- first\n  ,b\n)" in out

    def test_view_column_list(self):
        out, _ = format_sql("CREATE VIEW v (c, d) AS SELECT 1, 2")
        assert out.startswith("CREATE VIEW v (c, d) AS\n")


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


class TestStringLiteralLineBreaks:
    """A string literal's line breaks are part of its value and never re-indented (#384)."""

    @pytest.mark.parametrize(
        ("sql", "literal"),
        [
            ("SELECT 'a' || if(x = 1, 'one\ntwo', 'b') AS v FROM t", "'one\ntwo'"),
            ("SELECT CASE WHEN x = 1 THEN 'a\nb' WHEN x = 2 THEN 'c' END AS v FROM t", "'a\nb'"),
            ("SELECT t.a FROM t INNER JOIN u ON u.s = 'x\ny' AND u.id = t.id", "'x\ny'"),
            ("SELECT string_agg(a, '\n') AS s FROM t GROUP BY ALL", "'\n'"),
            ("SELECT k AS kk, (SELECT max(v) FROM u WHERE u.s = 'p\nq') AS w FROM t", "'p\nq'"),
        ],
    )
    def test_literal_in_a_compact_expression_keeps_its_lines(self, sql, literal):
        once, _ = format_sql(sql)
        assert literal in once
        assert format_sql(once)[0] == once

    def test_column_ending_in_a_literal_aligns_on_its_own(self):
        out, _ = format_sql("SELECT 'ab\ncdefghijklmnop' AS s, b AS bb, ccc AS c FROM t")
        assert "   'ab\ncdefghijklmnop' AS s\n  ,b   AS bb\n  ,ccc AS c\n" in out
        assert format_sql(out)[0] == out

    def test_unaliased_literal_does_not_widen_the_alignment(self):
        out, _ = format_sql("SELECT 'x\ny', bbb AS b, c AS cc FROM t")
        assert "  ,bbb AS b\n  ,c   AS cc\n" in out

    def test_case_with_a_literal_in_a_branch_still_aligns_by_its_end(self):
        out, _ = format_sql(
            "SELECT CASE WHEN x = 1 THEN 'a\nb' WHEN x = 2 THEN 'c' END AS v, bbbbbbbbbbbbbbbbbbbb AS b FROM t"
        )
        assert "   END                  AS v\n  ,bbbbbbbbbbbbbbbbbbbb AS b\n" in out


class TestCompactSubqueryAlias:
    """A SELECT rendered on one line doesn't take the enclosing list's alias padding (#384)."""

    def test_compact_scalar_subquery_alias_is_not_padded(self):
        sql = "SELECT k AS kk, CASE WHEN y = 1 THEN (SELECT max(v) AS m FROM u) WHEN y = 2 THEN 2 END AS w FROM t"
        out, _ = format_sql(sql, JarifyConfig(min_column_alias=34))
        assert "     THEN (SELECT MAX(v) AS m FROM u)\n" in out
        assert format_sql(out, JarifyConfig(min_column_alias=34))[0] == out

    def test_multi_line_subquery_still_aligns_its_own_list(self):
        sql = "SELECT k AS kk, (SELECT max(v) AS m FROM u) AS w FROM t"
        out, _ = format_sql(sql, JarifyConfig(min_column_alias=34))
        assert "       MAX(v)                      AS m\n" in out


class TestInListWrapping:
    LONG = (
        "('NLD', 'DEU', 'POL', 'ISR', 'FRA', 'GBR', 'ITA', 'ESP', 'AUT', 'BEL', 'SWE', "
        "'CHE', 'ROU', 'CZE', 'DNK', 'PRT', 'FIN', 'HUN', 'GRC', 'UKR', 'IRL', 'NOR')"
    )

    def test_long_in_list_puts_one_value_per_line(self):
        out, _ = format_sql(f"SELECT a FROM t WHERE c IN {self.LONG}")
        assert "WHERE c IN (\n   'NLD'\n  ,'DEU'\n" in out
        assert "\n  ,'NOR'\n)\n;" in out

    def test_long_not_in_list_after_and_indents_under_the_condition(self):
        out, _ = format_sql(f"SELECT a FROM t WHERE x = 1 AND c NOT IN {self.LONG} AND y = 2")
        assert "  AND c NOT IN (\n     'NLD'\n    ,'DEU'\n" in out
        assert "\n    ,'NOR'\n  )\n  AND y = 2\n" in out

    def test_in_list_wraps_when_the_whole_expression_is_too_wide(self):
        column = "a_really_quite_long_column_name_that_pushes_the_line_past_the_limit"
        values = "('value_one', 'value_two', 'value_three', 'value_four', 'value_five')"
        out, _ = format_sql(f"SELECT a FROM t WHERE {column} IN {values}")
        assert f"WHERE {column} IN (\n   'value_one'\n  ,'value_two'\n" in out
        # With a short column name the same values fit on the line.
        out, _ = format_sql(f"SELECT a FROM t WHERE c IN {values}")
        assert f"WHERE c IN {values}\n" in out

    def test_long_in_list_with_trailing_commas(self):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        out, _ = format_sql(f"SELECT a FROM t WHERE c IN {self.LONG}", config)
        assert "WHERE c IN (\n  'NLD',\n  'DEU',\n" in out
        assert "\n  'NOR'\n)\n;" in out

    def test_long_list_literal_puts_one_item_per_line(self):
        items = ", ".join(f"'item_number_{i:02d}'" for i in range(8))
        out, _ = format_sql(f"SELECT [{items}] AS l")
        assert "   [\n     'item_number_00'\n    ,'item_number_01'\n" in out
        assert "\n    ,'item_number_07'\n  ] AS l" in out

    def test_long_pivot_in_list_stays_on_the_for_line(self):
        values = ", ".join(f"'category_number_{i:02d}'" for i in range(6))
        out, _ = format_sql(f"FROM t PIVOT (SUM(amount) FOR category IN ({values}))")
        assert "PIVOT(SUM(amount) FOR category IN (\n   'category_number_00'\n" in out
        assert "\n  ,'category_number_05'\n))" in out

    def test_pivot_fields_are_not_separated_by_commas(self):
        # Wrapping the space-separated FOR fields in leading-comma style wrote
        # `,b IN (…)`, which DuckDB rejects.
        a = ", ".join(f"'a_value_number_{i:02d}'" for i in range(3))
        b = ", ".join(f"'b_value_number_{i:02d}'" for i in range(3))
        out, _ = format_sql(f"FROM t PIVOT (SUM(amount) FOR a IN ({a}) b IN ({b}))")
        assert f"FOR a IN ({a}) b IN ({b}))" in out

    def test_wrapped_in_lists_are_idempotent(self):
        sql = f"SELECT c IN {self.LONG} AS eu, [{self.LONG[1:-1]}] AS l FROM t WHERE c NOT IN {self.LONG}"
        once, _ = format_sql(sql)
        assert format_sql(once)[0] == once


class TestNotAfterOperand:
    """NOT IN, NOT BETWEEN, NOT SIMILAR TO and NOT GLOB keep NOT after the operand (#379)."""

    def test_not_in_and_not_between_keep_not_after_the_operand(self):
        out, _ = format_sql(
            "SELECT a FROM t WHERE a NOT IN (SELECT b FROM u) AND c NOT LIKE 'x%' AND d NOT BETWEEN 1 AND 2"
        )
        assert "WHERE a NOT IN (SELECT b FROM u)\n  AND c NOT LIKE 'x%'\n  AND d NOT BETWEEN 1 AND 2\n" in out

    def test_leading_not_is_written_after_the_operand_unless_parenthesized(self):
        sql = "SELECT a FROM t WHERE NOT a IN (1, 2) AND NOT d BETWEEN 1 AND 2 AND NOT (b IN (3)) AND NOT (c > 3)"
        out, _ = format_sql(sql)
        assert "WHERE a NOT IN (1, 2)\n  AND d NOT BETWEEN 1 AND 2\n  AND NOT (b IN (3))\n  AND NOT (c > 3)\n" in out

    def test_not_similar_to_and_not_glob_keep_not_after_the_operand(self):
        sql = (
            "SELECT a NOT SIMILAR TO 'x.*' AS s, b NOT GLOB 'x*' AS g, c NOT ILIKE 'x' AS i, "
            "d IS NOT DISTINCT FROM e AS d, f IS NOT NULL AS n, NOT f AS f2, NOT EXISTS (SELECT 1 FROM u) AS x FROM t"
        )
        out, _ = format_sql(sql)
        for text in ("a NOT SIMILAR TO 'x.*'", "b NOT GLOB 'x*'"):
            assert text in out
        # The negations sqlglot already keeps in place are unchanged.
        for text in ("c NOT ILIKE 'x'", "d IS NOT DISTINCT FROM e", "f IS NOT NULL", "NOT f ", "NOT EXISTS("):
            assert text in out

    def test_not_in_in_a_select_list_join_filter_and_case(self):
        sql = (
            "SELECT CASE WHEN a NOT IN (1) THEN 1 WHEN a NOT BETWEEN 2 AND 3 THEN 2 END AS c, "
            "COUNT(*) FILTER (WHERE b NOT IN (1)) AS n FROM t INNER JOIN u ON u.a = t.a AND u.b NOT IN (1, 2)"
        )
        out, _ = format_sql(sql)
        for text in (
            "WHEN a NOT IN (1)",
            "WHEN a NOT BETWEEN 2 AND 3",
            "FILTER(WHERE b NOT IN (1))",
            "ON u.a = t.a AND u.b NOT IN (1, 2)",
        ):
            assert text in out

    def test_long_not_in_subquery_takes_the_block_form(self):
        subquery = (
            "SELECT user_id FROM excluded_users "
            "WHERE excluded_reason = 'a reason long enough to put the subquery on its own lines'"
        )
        out, _ = format_sql(f"SELECT a FROM t WHERE user_id NOT IN ({subquery})")
        assert "WHERE user_id NOT IN\n(\n  SELECT\n     user_id\n" in out

    def test_own_line_comment_before_not_in_goes_above_where(self):
        out, _ = format_sql("SELECT a FROM t WHERE\n-- only active\na NOT IN (1, 2)\nAND b = 1")
        assert "FROM t\n-- only active\nWHERE a NOT IN (1, 2)\n  AND b = 1\n" in out

    def test_not_in_is_idempotent(self):
        once, _ = format_sql(
            "SELECT NOT a IN (1) AS x FROM t WHERE NOT b BETWEEN 1 AND 2 OR c NOT IN (SELECT c FROM u)"
        )
        assert "a NOT IN (1)" in once
        assert format_sql(once)[0] == once


class TestConditionLinesAfterConnector:
    """A multi-line condition after OR / AND keeps its lines under its connector (#379)."""

    VALUES = ", ".join(f"'value_number_{i:02d}'" for i in range(7))

    def _values(self, column: int) -> list[str]:
        """The wrapped VALUES, with the first value's text starting at *column*."""
        return [
            f"{' ' * column}'value_number_00'",
            *(f"{' ' * (column - 1)},'value_number_{i:02d}'" for i in range(1, 7)),
        ]

    def test_in_list_after_or_is_indented_under_the_or(self):
        out, _ = format_sql(f"SELECT a FROM t WHERE a = 1 OR b IN ({self.VALUES})")
        assert "\n".join(["WHERE a = 1", "   OR b IN (", *self._values(6), "   )", ";"]) in out

    def test_in_list_after_or_with_trailing_commas(self):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        out, _ = format_sql(f"SELECT a FROM t WHERE a = 1 OR b IN ({self.VALUES})", config)
        assert "WHERE a = 1\n   OR b IN (\n     'value_number_00',\n     'value_number_01',\n" in out
        assert "\n     'value_number_06'\n   )\n;" in out

    def test_in_subquery_after_or_is_indented_under_the_or(self):
        subquery = (
            "SELECT user_id FROM excluded_users "
            "WHERE excluded_reason = 'a reason long enough to put the subquery on its own lines'"
        )
        out, _ = format_sql(f"SELECT a FROM t WHERE a = 1 OR b IN ({subquery})")
        assert "WHERE a = 1\n   OR b IN\n   (\n     SELECT\n        user_id\n" in out
        assert "\n   )\n;" in out

    def test_in_list_in_having_is_indented_under_its_connector(self):
        out, _ = format_sql(f"SELECT a, COUNT(*) AS n FROM t GROUP BY ALL HAVING COUNT(*) = 1 OR a IN ({self.VALUES})")
        assert "\n".join(["HAVING COUNT(*) = 1", "    OR a IN (", *self._values(7), "    )"]) in out
        out, _ = format_sql(f"SELECT a, COUNT(*) AS n FROM t GROUP BY ALL HAVING COUNT(*) = 1 AND a IN ({self.VALUES})")
        assert "\n".join(["HAVING COUNT(*) = 1", "   AND a IN (", *self._values(6), "   )"]) in out

    def test_in_list_in_commented_join_condition_is_indented_under_the_or(self):
        out, _ = format_sql(f"SELECT a FROM t INNER JOIN u ON u.a = t.a -- same\nOR u.b IN ({self.VALUES})")
        # OR is right-aligned under ON, so the condition after it starts where the first one does.
        or_column = len("INNER JOIN u ON ") - len("OR ")
        expected = [f"{' ' * or_column}OR u.b IN (", *self._values(or_column + 3), f"{' ' * or_column})"]
        assert "\n".join(expected) in out

    def test_in_list_in_case_condition_is_indented_under_the_or(self):
        sql = f"SELECT CASE WHEN a = 1 OR b IN ({self.VALUES}) THEN 'x' WHEN a = 2 THEN 'y' END AS z FROM t"
        out, _ = format_sql(sql)
        assert "\n".join(["     WHEN a = 1", "       OR b IN (", *self._values(10), "       )", "     THEN 'x'"]) in out

    def test_in_list_after_a_case_first_when_closes_under_the_when(self):
        # As after WHERE: the values three columns past the keyword, ) under it (#382).
        sql = f"SELECT CASE WHEN b IN ({self.VALUES}) THEN 'x' WHEN a = 2 THEN 'y' END AS z FROM t"
        out, _ = format_sql(sql)
        assert "\n".join(["     WHEN b IN (", *self._values(8), "     )", "     THEN 'x'"]) in out
        assert format_sql(out)[0] == out

    def test_in_subquery_after_a_case_first_when_opens_under_the_when(self):
        subquery = (
            "SELECT user_id FROM excluded_users "
            "WHERE excluded_reason = 'a reason long enough to put the subquery on its own lines'"
        )
        out, _ = format_sql(f"SELECT CASE WHEN b NOT IN ({subquery}) THEN 'x' WHEN a = 2 THEN 'y' END AS z FROM t")
        assert "     WHEN b NOT IN\n     (\n       SELECT\n          user_id\n" in out
        assert "\n     )\n     THEN 'x'\n" in out

    def test_parentheses_after_a_case_first_when_close_under_the_when(self):
        condition = "a = 1 OR some_long_column_name_aaaaaaaa = " + "_".join(["some_long_table_name"] + ["x" * 20] * 3)
        out, _ = format_sql(f"SELECT CASE WHEN ({condition}) THEN 'x' WHEN a = 2 THEN 'y' END AS z FROM t")
        assert "     WHEN (\n       a = 1\n       OR some_long_column_name_aaaaaaaa = " in out
        assert "\n     )\n     THEN 'x'\n" in out

    def test_in_list_in_a_case_in_where_closes_under_its_when(self):
        sql = f"SELECT a FROM t WHERE CASE WHEN b IN ({self.VALUES}) THEN 1 WHEN c THEN 2 END = 1"
        out, _ = format_sql(sql)
        assert "\n".join(["WHERE CASE", "        WHEN b IN (", *self._values(11), "        )", "        THEN 1"]) in out

    def test_wrapped_conditions_after_or_are_idempotent(self):
        sql = (
            f"SELECT CASE WHEN a = 1 OR b IN ({self.VALUES}) THEN 1 WHEN a = 2 THEN 2 END AS z FROM t "
            f"WHERE a = 1 OR (c = 2 AND b IN ({self.VALUES})) OR b IN ({self.VALUES})"
        )
        once, _ = format_sql(sql)
        assert "\n   OR (\n     c = 2\n     AND b IN (\n        'value_number_00'\n" in once
        assert format_sql(once)[0] == once


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
        assert "  ,STRING_AGG(\n     a\n    ,',' ORDER BY b -- abc\n  ) AS s" in result

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


class TestFunctionCaseOverrides:
    SQL = (
        "SELECT string_agg(a, ',') AS s, any_value(b) AS v, list(c) AS l, arg_max(e, f) AS am, "
        "lag(j) OVER () AS lg, regexp_extract(x, 'y') AS r FROM t"
    )

    def test_default_classification_is_unchanged(self):
        out, _ = format_sql(self.SQL)
        assert out == (
            "SELECT\n"
            "   STRING_AGG(a, ',')     AS s\n"
            "  ,ANY_VALUE(b)           AS v\n"
            "  ,list(c)                AS l\n"
            "  ,ARG_MAX(e, f)          AS am\n"
            "  ,LAG(j) OVER ()         AS lg\n"
            "  ,regexp_extract(x, 'y') AS r\n"
            "FROM t\n"
            ";\n"
        )

    def test_lists_override_builtin_case_in_both_directions(self):
        config = JarifyConfig(uppercase_functions=["list", "regexp_extract"], lowercase_functions=["any_value", "lag"])
        out, _ = format_sql(self.SQL, config)
        assert out == (
            "SELECT\n"
            "   STRING_AGG(a, ',')     AS s\n"
            "  ,any_value(b)           AS v\n"
            "  ,LIST(c)                AS l\n"
            "  ,ARG_MAX(e, f)          AS am\n"
            "  ,lag(j) OVER ()         AS lg\n"
            "  ,REGEXP_EXTRACT(x, 'y') AS r\n"
            "FROM t\n"
            ";\n"
        )

    def test_names_match_case_insensitively(self):
        config = JarifyConfig(uppercase_functions=["LiSt"], lowercase_functions=["ANY_VALUE"])
        out, _ = format_sql("SELECT List(a) AS l, Any_Value(b) AS v FROM t", config)
        assert "LIST(a) " in out
        assert "any_value(b) " in out

    def test_override_applies_to_canonical_renames(self):
        config = JarifyConfig(uppercase_functions=["list"], lowercase_functions=["string_agg"])
        out, _ = format_sql("SELECT array_agg(a ORDER BY a) AS l, listagg(b, ',') AS s FROM t", config)
        assert "LIST(a ORDER BY a) " in out
        assert "string_agg(b, ',') " in out

    def test_override_applies_to_list_distinct_wrapping(self):
        config = JarifyConfig(uppercase_functions=["list"], max_line_length=40)
        sql = "SELECT array_agg(DISTINCT some_long_column_name || another_long_column_name) AS l FROM t"
        out, _ = format_sql(sql, config)
        assert "LIST(\n" in out
        assert format_sql(out, config)[0] == out

    def test_override_applies_to_ifnull_written_and_rewritten(self):
        config = JarifyConfig(uppercase_functions=["ifnull"])
        out, _ = format_sql("SELECT ifnull(a, 0) AS x, coalesce(b, 0) AS y FROM t", config)
        assert "IFNULL(a, 0) " in out
        assert "IFNULL(b, 0) " in out
        assert "ifnull" not in out

    def test_override_applies_to_if_inline_and_wrapped(self):
        config = JarifyConfig(uppercase_functions=["if"])
        out, _ = format_sql("SELECT CASE WHEN a THEN 1 ELSE 0 END AS x, if(b, 1, 2) AS y FROM t", config)
        assert "IF(a, 1, 0) " in out
        assert "IF(b, 1, 2) " in out
        wide = (
            "SELECT if(some_really_long_column_name_one > 100 AND another_really_long_column_name_two < 200, "
            "'a_long_true_branch_value', 'a_long_false_branch_value_xxxxxxxxxxxxxxxxxx') AS x FROM t"
        )
        out, _ = format_sql(wide, config)
        assert "   IF(\n" in out

    def test_user_macros_keep_default_case_unless_listed(self):
        config = JarifyConfig(uppercase_functions=["my_macro"])
        out, _ = format_sql("SELECT my_macro(a) AS m, other_macro(b) AS o, main.my_macro(c) AS q FROM t", config)
        assert "MY_MACRO(a) " in out
        assert "other_macro(b) " in out
        assert "main.my_macro(c) " in out

    def test_sqlmesh_macro_calls_are_not_changed(self):
        config = JarifyConfig(uppercase_functions=["my_macro", "each"])
        out, warnings = format_sql("MODEL (name a.b);\nselect @my_macro(a) as m, @each(b) as e from t\n", config)
        assert not warnings
        assert "@my_macro(a) " in out
        assert "@each(b) " in out

    def test_overrides_are_idempotent(self):
        config = JarifyConfig(uppercase_functions=["list", "ifnull", "if"], lowercase_functions=["any_value"])
        sql = "SELECT array_agg(a) AS l, ifnull(b, 0) AS i, if(c, 1, 2) AS f, any_value(d) AS v FROM t"
        out, _ = format_sql(sql, config)
        assert format_sql(out, config)[0] == out


class TestPreferIfOverCaseNesting:
    def test_rewrites_a_case_nested_in_else_in_one_pass(self):
        out, _ = format_sql("SELECT CASE WHEN x THEN 1 ELSE CASE WHEN c THEN 4 ELSE 5 END END AS k FROM t")
        assert out == "SELECT\n   if(x, 1, if(c, 4, 5)) AS k\nFROM t\n;\n"

    def test_rewrites_a_case_nested_in_then_in_one_pass(self):
        out, _ = format_sql("SELECT CASE WHEN x THEN CASE WHEN c THEN 4 END ELSE 0 END AS k FROM t")
        assert out == "SELECT\n   if(x, if(c, 4, NULL), 0) AS k\nFROM t\n;\n"

    def test_rewrites_a_case_nested_in_a_multi_when_case(self):
        out, _ = format_sql("SELECT CASE WHEN a = 1 THEN CASE WHEN b THEN 1 ELSE 2 END WHEN a = 2 THEN 3 END AS k")
        assert "THEN if(b, 1, 2)\n" in out
        assert out.count("CASE") == 1

    def test_keeps_a_case_that_carries_a_comment(self):
        # The comment is attached to the inner CASE itself; an IF() call would
        # drop it, so the inner CASE stays a CASE and the comment is kept.
        sql = "SELECT CASE WHEN q = 1 THEN 0 ELSE\n  -- why\n  CASE WHEN c THEN 4 ELSE 5 END END AS k FROM t\n"
        out, _ = format_sql(sql)
        assert "-- why" in out
        assert "if(" not in out
        assert format_sql(out)[0] == out


def _case_layout(sql: str, which: int = 0) -> list[tuple[int, str]]:
    """Return each line of a CASE in sql as (column offset from CASE, leading text).

    *which* picks the line the CASE starts on, among the lines holding
    ``CASE``: the first by default, ``-1`` for the last (a nested CASE). The
    END line keeps only ``END``, so what follows it (an alias, a comma, a
    closing paren) doesn't matter.
    """
    lines = sql.splitlines()
    start = [i for i, line in enumerate(lines) if "CASE" in line][which]
    column = lines[start].index("CASE")
    layout = [(0, lines[start][column:])]
    for line in lines[start + 1 :]:
        text = line.strip()
        offset = len(line) - len(line.lstrip()) - column
        if text.startswith("END"):
            layout.append((offset, "END"))
            return layout
        layout.append((offset, text))
    raise AssertionError(f"no END in:\n{sql}")


class TestCaseInFunctionArgs:
    SEARCHED = "CASE WHEN a THEN 1 WHEN b THEN 2 ELSE 3 END"
    SIMPLE = "CASE k WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'other' END"

    @pytest.mark.parametrize("case", [SEARCHED, SIMPLE], ids=["searched", "simple"])
    @pytest.mark.parametrize(
        "call",
        ["if(x, {case}, 0)", "if({case}, 1, 0)", "format('{}', x, {case})", "format({case}, x)", "SUM({case})"],
    )
    def test_case_argument_is_laid_out_as_in_a_select_list(self, call, case):
        expected = _case_layout(format_sql(f"SELECT {case} AS c FROM t")[0])
        out, _ = format_sql(f"SELECT {call.replace('{case}', case)} AS c FROM t")
        assert _case_layout(out) == expected
        assert format_sql(out)[0] == out

    def test_case_in_wrapped_if_lines_up_under_case(self):
        sql = (
            "SELECT if(p.entry_type_id = 3, CASE WHEN regexp_full_match(p.description, '^B2S.*$') "
            "THEN 'b2s_order' WHEN regexp_full_match(p.description, '^.*special.*$') THEN 'special_order' "
            "ELSE 'unknown' END, 'nomination') AS kind FROM p"
        )
        out, _ = format_sql(sql)
        assert "     ,CASE\n        WHEN regexp_full_match(p.description, '^B2S.*$')\n" in out
        assert "        ELSE 'unknown'\n      END\n     ,'nomination'\n" in out

    def test_case_makes_a_one_line_if_wrap(self):
        out, _ = format_sql("SELECT if(x, CASE WHEN a THEN 1 WHEN b THEN 2 ELSE 3 END, 0) AS k FROM t")
        assert out == (
            "SELECT\n"
            "   if(\n"
            "      x\n"
            "     ,CASE\n"
            "        WHEN a\n"
            "        THEN 1\n"
            "        WHEN b\n"
            "        THEN 2\n"
            "        ELSE 3\n"
            "      END\n"
            "     ,0\n"
            "  ) AS k\n"
            "FROM t\n"
            ";\n"
        )

    def test_other_arguments_keep_their_wrapped_if_layout(self):
        # Only a CASE moves; a parenthesised argument still closes under its "(".
        sql = (
            "SELECT if(condition_that_makes_the_call_too_wide, (very_long_value_a_xxxxxxxxxxxxxxxxx, "
            "very_long_value_b_xxxxxxxxxxxxxxxxxxxxxxxx, very_long_value_c_xxxxxxxxxxxxx)::some_type, fallback) AS r"
        )
        out, _ = format_sql(sql)
        assert "\n     ,(\n         very_long_value_a_xxxxxxxxxxxxxxxxx\n" in out
        assert "\n      )::some_type\n" in out


_SEARCHED_CASE = "CASE WHEN x = 1 THEN 'one' WHEN x = 2 THEN 'two' ELSE 'many' END"
_SIMPLE_CASE = "CASE k WHEN 1 THEN 'one' WHEN 2 THEN 'two' ELSE 'many' END"
_CASE_FORMS = pytest.mark.parametrize("case", [_SEARCHED_CASE, _SIMPLE_CASE], ids=["searched", "simple"])
# Statements with a CASE in some position, at {case}
_CASE_POSITIONS = {
    "then": "SELECT CASE WHEN y = 1 THEN {case} WHEN y = 2 THEN 'b' END AS v FROM t",
    "else": "SELECT CASE WHEN y = 1 THEN 'a' WHEN y = 2 THEN 'b' ELSE {case} END AS v FROM t",
    "simple_case_then": "SELECT CASE j WHEN 1 THEN {case} WHEN 2 THEN 'b' END AS v FROM t",
    "when": "SELECT CASE WHEN {case} = 'one' THEN 1 WHEN y = 2 THEN 2 END AS v FROM t",
    "string_agg": "SELECT STRING_AGG({case}, ', ') AS v FROM t",
    "parens_concat": "SELECT ({case}) || 'x' AS v FROM t",
    "parens_cast": "SELECT ({case})::text AS v FROM t",
    "after_operator": "SELECT 'a' || {case} AS v FROM t",
    "count_distinct": "SELECT COUNT(DISTINCT {case}) AS v FROM t",
    "window_order_by": "SELECT ROW_NUMBER() OVER (PARTITION BY a ORDER BY {case}) AS n FROM t",
    "window_partition_by": "SELECT ROW_NUMBER() OVER (PARTITION BY {case} ORDER BY a) AS n FROM t",
    "aggregate_order_by": "SELECT list(a ORDER BY {case}) AS l FROM t",
    "where": "SELECT a FROM t WHERE {case} = 'one'",
    "where_and": "SELECT a FROM t WHERE a = 1 AND {case} = 'one'",
    "where_or": "SELECT a FROM t WHERE a = 1 OR {case} = 'one'",
    "having": "SELECT a FROM t GROUP BY ALL HAVING {case} = 'one'",
    "qualify": "SELECT a FROM t QUALIFY {case} = 'one'",
    "join_on": "SELECT a FROM t JOIN u ON u.k = {case}",
    "in_subquery": "SELECT a FROM t WHERE a IN (SELECT {case} FROM u)",
    "in_list": "SELECT x IN ('a', {case}) AS b FROM t",
}
# With trailing commas there's no leading comma for a simple CASE's END to go
# under, so END goes under CASE in both forms.
_TRAILING_CASE_LAYOUTS = {
    _SEARCHED_CASE: [
        (0, "CASE"),
        (2, "WHEN x = 1"),
        (2, "THEN 'one'"),
        (2, "WHEN x = 2"),
        (2, "THEN 'two'"),
        (2, "ELSE 'many'"),
        (0, "END"),
    ],
    _SIMPLE_CASE: [(0, "CASE k"), (2, "WHEN 1 THEN 'one'"), (2, "WHEN 2 THEN 'two'"), (2, "ELSE 'many'"), (0, "END")],
}
_TRAILING_CASE_CASES = [
    pytest.param("SELECT a, {case} AS v, b FROM t", _SEARCHED_CASE, id="select_list-searched"),
    *(
        pytest.param(_CASE_POSITIONS[name], case, id=f"{name}-{form}")
        for name in ("then", "where", "window_order_by")
        for case, form in ((_SEARCHED_CASE, "searched"), (_SIMPLE_CASE, "simple"))
    ),
]


class TestCaseLayoutPositions:
    """A CASE is laid out as in a SELECT list, relative to its CASE keyword, wherever it appears (#377)."""

    @_CASE_FORMS
    @pytest.mark.parametrize("sql", _CASE_POSITIONS.values(), ids=_CASE_POSITIONS.keys())
    def test_case_is_laid_out_under_its_keyword(self, sql, case):
        expected = _case_layout(format_sql(f"SELECT {case} AS c FROM t")[0])
        out, _ = format_sql(sql.replace("{case}", case))
        assert _case_layout(out, which=-1) == expected
        assert format_sql(out)[0] == out

    @pytest.mark.parametrize(("sql", "case"), _TRAILING_CASE_CASES)
    def test_trailing_commas(self, sql, case):
        config = JarifyConfig(leading_commas=False, trailing_commas=True)
        out, _ = format_sql(sql.replace("{case}", case), config)
        assert _case_layout(out, which=-1) == _TRAILING_CASE_LAYOUTS[case]
        assert format_sql(out, config)[0] == out

    def test_nested_case_in_then_lines_up_under_its_keyword(self):
        out, _ = format_sql(_CASE_POSITIONS["then"].replace("{case}", _SEARCHED_CASE))
        assert out == (
            "SELECT\n"
            "   CASE\n"
            "     WHEN y = 1\n"
            "     THEN CASE\n"
            "            WHEN x = 1\n"
            "            THEN 'one'\n"
            "            WHEN x = 2\n"
            "            THEN 'two'\n"
            "            ELSE 'many'\n"
            "          END\n"
            "     WHEN y = 2\n"
            "     THEN 'b'\n"
            "   END AS v\n"
            "FROM t\n"
            ";\n"
        )

    def test_case_in_window_order_by_wraps_the_window_one_key_per_line(self):
        out, _ = format_sql(_CASE_POSITIONS["window_order_by"].replace("{case}", _SEARCHED_CASE))
        assert "   ROW_NUMBER() OVER (\n     PARTITION BY a\n     ORDER BY\n        CASE\n          WHEN x = 1\n" in out
        assert "          ELSE 'many'\n        END\n  ) AS n\n" in out

    def test_case_in_where_lines_up_after_the_keyword(self):
        out, _ = format_sql(f"SELECT a FROM t WHERE {_SEARCHED_CASE} = 'one' AND b = 2")
        assert "WHERE CASE\n        WHEN x = 1\n" in out
        assert "        ELSE 'many'\n      END = 'one'\n  AND b = 2\n" in out

    def test_case_on_the_left_of_where_equality_doesnt_pad_the_others(self):
        out, _ = format_sql(f"SELECT a FROM t WHERE a = 1 AND {_SEARCHED_CASE} = 'one'")
        assert "\nWHERE a = 1\n  AND CASE\n" in out

    def test_case_in_parentheses_keeps_them_around_it(self):
        out, _ = format_sql(f"SELECT ({_SEARCHED_CASE})::text AS v FROM t")
        assert "   (CASE\n      WHEN x = 1\n" in out
        assert "      ELSE 'many'\n    END)::text AS v\n" in out

    def test_case_in_string_agg_puts_each_argument_on_its_own_line(self):
        out, _ = format_sql(f"SELECT STRING_AGG({_SEARCHED_CASE}, ', ' ORDER BY y) AS v FROM t")
        assert "   STRING_AGG(\n     CASE\n       WHEN x = 1\n" in out
        assert "       ELSE 'many'\n     END\n    ,', '\n     ORDER BY y\n  ) AS v\n" in out

    def test_case_in_join_on_is_laid_out_like_where(self):
        out, _ = format_sql(f"SELECT a FROM t JOIN u ON u.k = {_SEARCHED_CASE} AND u.j = t.j")
        assert "INNER JOIN u ON u.k = CASE\n                        WHEN x = 1\n" in out
        assert "                      END\n            AND u.j = t.j\n" in out

    @pytest.mark.parametrize("case", [_SEARCHED_CASE, f"b || {_SEARCHED_CASE}"], ids=["case", "after_operator"])
    def test_aliases_line_up_after_a_case_end(self, case):
        out, _ = format_sql(f"SELECT a AS x, {case} AS y, c AS z FROM t")
        assert len(set(_as_columns(out, "x", "y", "z"))) == 1


_TRAILING_COMMAS = JarifyConfig(leading_commas=False, trailing_commas=True)


def _stable(out: str, config: JarifyConfig | None = None) -> bool:
    return format_sql(out, config)[0] == out


class TestColumnCommentsStayInPlace:
    """A comment written above, between or after columns stays there (#394)."""

    @pytest.mark.parametrize("column", ["ifnull(a, 1)", "f(a)", "(c + 1)", "x.title_case()"])
    def test_comment_between_columns_after_a_column_ending_in_a_paren(self, column):
        # sqlglot gives the comma's comment to the column before it, whatever
        # that column ends in; it was taken for a comment above that column.
        out, _ = format_sql(f"SELECT\n   {column}\n  -- c1\n  ,x AS y\nFROM t")
        assert f"   {column}\n  -- c1\n  ,x AS y\n" in out
        assert _stable(out)

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("SELECT a FROM t GROUP BY\n   f(a)\n  -- c1\n  ,b", "GROUP BY\n   f(a)\n  -- c1\n  ,b\n"),
            ("SELECT a FROM t ORDER BY\n   f(a)\n  -- c1\n  ,b", "ORDER BY\n   f(a)\n  -- c1\n  ,b\n"),
            ("SELECT a FROM t WHERE x IN (\n   f(a)\n  -- c1\n  ,b)", "WHERE x IN (\n   f(a)\n  -- c1\n  ,b\n)\n"),
        ],
        ids=["group_by", "order_by", "in_list"],
    )
    def test_comment_between_items_after_an_item_ending_in_a_paren(self, sql, expected):
        out, _ = format_sql(sql)
        assert expected in out
        assert _stable(out)

    @pytest.mark.parametrize(
        ("column", "rendered"),
        [
            ("-a", "-a"),
            ("~a", "~a"),
            ("x.title_case()", "x.title_case()"),
            ("t.x.upper()", "t.x.upper()"),
            ("-f(a)", "-f(a)"),
            ("-(a + 1)", "-(a + 1)"),
            ("INTERVAL 1 DAY", "INTERVAL '1' DAY"),
            ("DATE '2020-01-01'", "'2020-01-01'::date"),
        ],
    )
    @pytest.mark.parametrize("alias", ["", " AS v"])
    def test_comment_above_the_first_column_is_kept(self, column, rendered, alias):
        # sqlglot dropped a comment on a unary operator, on the column a
        # method is called on, and on INTERVAL or a typed literal's type.
        out, _ = format_sql(f"SELECT\n  -- c1\n  {column}{alias}\n  ,z\nFROM t")
        assert f"SELECT\n   -- c1\n   {rendered}" in out
        assert _stable(out)

    def test_comment_above_a_star_is_kept(self):
        out, _ = format_sql("SELECT\n  -- c1\n  * EXCLUDE (a)\nFROM t")
        assert "SELECT\n   -- c1\n   *\n   EXCLUDE (\n" in out
        assert _stable(out)

    @pytest.mark.parametrize(
        ("case", "rendered"),
        [
            ("CASE WHEN a THEN 1 ELSE 0 END", "if(a, 1, 0)"),
            ("CASE a WHEN 1 THEN 2 END", "CASE a\n    WHEN 1 THEN 2\n  END"),
        ],
        ids=["rewritten_to_if", "simple_case"],
    )
    def test_comment_after_a_case_stays_with_one_above_it(self, case, rendered):
        # sqlglot dropped the comment after END when the CASE took one from
        # above it.
        out, _ = format_sql(f"SELECT\n  -- c1\n  {case} -- c2\n  ,b\nFROM t")
        assert f"   -- c1\n   {rendered} -- c2\n  ,b\n" in out
        assert _stable(out)

    @pytest.mark.parametrize(
        ("column", "expected"),
        [
            ("a\n  -- c1\n  + 1", "   -- c1\n   a + 1\n  ,z\n"),
            ("a + -- c1\n   1", "   a + 1 -- c1\n  ,z\n"),
            ("a + 1\n  -- c1", "   a + 1\n  -- c1\n  ,z\n"),
            # An AND chain followed by a comment takes its multi-line form, as
            # it does on the next pass, when its last term holds the comment.
            ("a AND -- c1\n  b", "   a\n  AND b -- c1\n  ,z\n"),
        ],
        ids=["above_the_operator", "after_the_operator", "between_columns", "after_and"],
    )
    def test_comments_on_an_unaliased_operator_column_are_written_once(self, column, expected):
        # Like an aliased column's, which sqlglot moves onto the alias. They
        # were written after the operator and by the list too, one more copy
        # on every pass.
        out, _ = format_sql(f"SELECT\n   {column}\n  ,z\nFROM t")
        assert out.count("c1") == 1
        assert expected in out
        assert _stable(out)

    @pytest.mark.parametrize("operator", ["a *", "NOT"])
    def test_comment_above_a_parenthesis_after_an_operator_follows_it(self, operator):
        # Written before the parenthesis, it would follow the operator on its
        # line and belong to the operator on the next pass.
        out, _ = format_sql(f"SELECT {operator}\n-- c1\n(b + 1) AS v FROM t")
        assert f"   {operator} (b + 1) /* c1 */ AS v\n" in out
        assert _stable(out)

    def test_comments_on_bare_parenthesized_columns_are_kept(self):
        # A parenthesis rendered twice, once to measure it, dropped them.
        sql = "SELECT\n   z\n  ,(b + 1) -- c2\n  ,(c + 1)\n  -- c3\n  ,y AS w\n  ,v AS u\nFROM t"
        out, _ = format_sql(sql)
        assert "  ,(b + 1) -- c2\n  ,(c + 1)\n  -- c3\n  ,y" in out
        assert _stable(out)


class TestDroppedOperandComments:
    """Comments sqlglot drops where it rebuilds a node are kept (#394)."""

    @pytest.mark.parametrize(
        ("column", "rendered"),
        [
            ("a::my_type", "a::my_type"),
            ("b->>'key'", "b->>'key'"),
            ("INTERVAL 1 DAY", "INTERVAL '1' DAY"),
            ("SUM(b) OVER (PARTITION BY c)", "SUM(b) OVER (PARTITION BY c)"),
        ],
    )
    def test_comment_after_a_column_is_kept(self, column, rendered):
        out, _ = format_sql(f"SELECT\n  -- c1\n  {column} -- c2\n  ,z\nFROM t")
        assert f"   -- c1\n   {rendered} -- c2\n  ,z\n" in out
        assert _stable(out)

    @pytest.mark.parametrize("call", ["list_filter(l, lambda c: regexp_matches(c, 'x')", "f(regexp_matches(c, 'x')"])
    def test_comment_after_a_binary_node_written_as_a_function_is_kept(self, call):
        # regexp_matches is a binary node, whose comments sqlglot writes only
        # after an operator, and it has none.
        out, _ = format_sql(f"SELECT {call} -- c1\n) AS v FROM t")
        assert "regexp_matches(c, 'x') -- c1\n" in out
        assert _stable(out)

    def test_comment_above_a_lambda_argument_is_kept(self):
        out, _ = format_sql("SELECT list_transform(k,\n  -- c1\n  lambda x: x + 1) AS v FROM t")
        assert out.count("-- c1") == 1
        assert _stable(out)

    def test_comment_on_a_rebuilt_function_argument_is_kept(self):
        # date_trunc's builder turns its unit into a keyword.
        out, _ = format_sql("SELECT date_trunc('week' -- c1\n, d) AS v FROM t")
        assert out.count("-- c1") == 1
        assert _stable(out)

    def test_comment_after_a_tuples_paren_is_kept(self):
        out, _ = format_sql("SELECT ( -- c1\n a.x, a.y)::point_type AS v FROM t")
        assert "   (\n     a.x -- c1\n    ,a.y\n  )::point_type AS v\n" in out
        assert _stable(out)

    def test_comment_before_an_equals_in_qualify_is_kept(self):
        sql = "SELECT a FROM t QUALIFY\n  -- c1\n  ROW_NUMBER() OVER (ORDER BY b) /* c2 */ = 1\n  AND a > 2"
        out, _ = format_sql(sql)
        assert "QUALIFY\n  -- c1\n  ROW_NUMBER() OVER (ORDER BY b) /* c2 */ = 1\n  AND a > 2\n" in out
        assert _stable(out)

    def test_comment_on_an_aligned_where_equals_is_kept(self):
        out, _ = format_sql("SELECT a FROM t WHERE a = /* c1 */ 1 AND bb = 2")
        assert "WHERE a  = /* c1 */ 1\n  AND bb = 2\n" in out
        assert _stable(out)

    @pytest.mark.parametrize("cross_join", ["warn", "off"])
    def test_comment_on_a_comma_join_is_kept(self, cross_join):
        config = JarifyConfig(no_implicit_cross_join=cross_join)
        out, _ = format_sql("SELECT a FROM t\n-- c1\n, u", config)
        assert "FROM t\n-- c1\n" in out
        assert _stable(out, config)

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("SELECT coalesce(b, c, a /* c1 */ /* c2 */) AS v FROM t", "    ,a /* c1 */ -- c2\n  ) AS v\n"),
            ("SELECT CAST(a /* c1 */ /* c2 */ AS int) AS v FROM t", "   a /* c1 */ /* c2 */::int AS v\n"),
            ("SELECT a FROM t WHERE x IN (1, 2 /* c1 */ /* c2 */)", "  ,2 /* c1 */ -- c2\n)\n"),
        ],
        ids=["last_argument", "cast", "last_in_list"],
    )
    def test_several_comments_after_a_value_stay_on_its_line(self, sql, expected):
        # On lines of their own, the comments after the first belonged to the
        # `)` or `::` after them on the next pass.
        out, _ = format_sql(sql)
        assert expected in out
        assert _stable(out)


class TestCreateTableColumnComments:
    """A comment above a CREATE TABLE column stays above it (#394)."""

    def test_comment_above_a_column_stays_above_it_outside_the_alignment(self):
        out, _ = format_sql("CREATE TABLE t (\n  id int,\n  -- c1\n  label text\n)")
        assert out == "CREATE TABLE t\n(\n   id    int\n  -- c1\n  ,label text\n)\n;\n"
        assert _stable(out)

    def test_comment_after_a_user_defined_type_is_kept(self):
        out, _ = format_sql("CREATE TABLE t (a my_type -- c1\n, b int)")
        assert "   a my_type -- c1\n  ,b int\n" in out
        assert _stable(out)


class TestTrailingCommaComments:
    """With trailing commas, comments around columns stay where they were written, as with leading commas (#394)."""

    @pytest.mark.parametrize("column", ["a + 1 AS v", "a", "CASE WHEN x THEN 1 WHEN y THEN 2 END AS w"])
    def test_comment_above_the_first_column_stays_above_it(self, column):
        out, _ = format_sql(f"SELECT\n  -- c1\n  {column},\n  b\nFROM t", _TRAILING_COMMAS)
        assert "SELECT\n  -- c1\n  " in out
        assert "/* c1 */" not in out
        assert _stable(out, _TRAILING_COMMAS)

    def test_comments_between_and_after_columns_stay_there(self):
        sql = "SELECT\n  a,\n  -- c1\n  b, -- c2\n  c\n  -- c3\n  , d\nFROM t"
        out, _ = format_sql(sql, _TRAILING_COMMAS)
        assert "  a,\n  -- c1\n  b, -- c2\n  c,\n  -- c3\n  d\n" in out
        assert _stable(out, _TRAILING_COMMAS)

    @pytest.mark.parametrize(
        ("sql", "expected"),
        [
            ("SELECT a FROM t WHERE c IN (\n  -- c1\n  1,\n  2)", "WHERE c IN (\n  -- c1\n  1,\n  2\n)\n"),
            ("SELECT a FROM t GROUP BY\n  a,\n  -- c1\n  b", "GROUP BY\n  a,\n  -- c1\n  b\n"),
            (
                "SELECT ROW_NUMBER() OVER (ORDER BY a,\n  -- c1\n  b) AS n FROM t",
                "       a,\n       -- c1\n       b\n",
            ),
        ],
        ids=["in_list", "group_by", "window_order_by"],
    )
    def test_comment_above_an_item_of_another_list_stays_above_it(self, sql, expected):
        out, _ = format_sql(sql, _TRAILING_COMMAS)
        assert expected in out
        assert _stable(out, _TRAILING_COMMAS)


class TestArraySubquery:
    """ARRAY(query) is laid out like a scalar subquery (#394)."""

    def test_query_goes_below_array_paren(self):
        out, _ = format_sql("SELECT array(SELECT a FROM u WHERE u.k = 1) AS v FROM t")
        assert out == "SELECT\n   array(\n    SELECT\n       a\n    FROM u\n    WHERE u.k = 1\n  ) AS v\nFROM t\n;\n"
        assert _stable(out)

    def test_query_with_a_with_goes_below_array_paren(self):
        out, _ = format_sql("SELECT array(WITH x AS (SELECT 1 AS a) SELECT a FROM x) AS v FROM t")
        assert "   array(\n    WITH x AS\n    (\n" in out
        assert "    FROM x\n  ) AS v\n" in out
        assert _stable(out)


class TestCaseBranchWrapping:
    """A CASE branch value that doesn't fit on its line takes its own layout (#394)."""

    # 115 columns: `THEN ` and it fit in 120, but not after the CASE's indentation too.
    _LONG = "(SELECT MAX(b) FROM u WHERE u.id = t.id AND u.kind = '" + "x" * 59 + "')"

    def test_long_then_value_wraps_with_its_paren_under_then(self):
        out, _ = format_sql(f"SELECT CASE WHEN a = 1 THEN {self._LONG} WHEN a = 2 THEN 3 END AS v FROM t")
        assert "     THEN (\n       SELECT\n          MAX(b)\n       FROM u\n" in out
        assert "\n     )\n     WHEN a = 2\n" in out
        assert _stable(out)

    def test_long_else_value_wraps_too(self):
        out, _ = format_sql(f"SELECT CASE WHEN a = 1 THEN 2 WHEN a = 2 THEN 3 ELSE {self._LONG} END AS v FROM t")
        assert "     ELSE (\n       SELECT\n" in out
        assert "\n     )\n   END AS v\n" in out
        assert _stable(out)

    def test_the_case_column_counts(self):
        # In a CTE the CASE starts further right, so a value that fits in the
        # main query doesn't fit there.
        # 10 + 108 columns in the main query, 14 + 108 in the CTE.
        value = "(SELECT MAX(b) FROM u WHERE u.id = t.id AND u.kind = '" + "x" * 52 + "')"
        main, _ = format_sql(f"SELECT CASE WHEN a = 1 THEN {value} WHEN a = 2 THEN 3 END AS v FROM t")
        nested, _ = format_sql(
            f"WITH _c AS (WITH _d AS (SELECT CASE WHEN a = 1 THEN {value} WHEN a = 2 THEN 3 END AS v FROM t) "
            "SELECT v FROM _d) SELECT v FROM _c"
        )
        assert f"     THEN {value}\n" in main
        assert "         THEN (\n" in nested
        assert all(len(line) <= 120 for line in nested.splitlines())

    def test_long_if_branch_wraps_too(self):
        # A single-branch CASE becomes if(), whose branches start four columns
        # past its name.
        out, _ = format_sql(f"SELECT CASE WHEN a = 1 THEN {self._LONG} ELSE 0 END AS v FROM t")
        assert "   if(\n      a = 1\n     ,(\n        SELECT\n" in out
        assert all(len(line) <= 120 for line in out.splitlines())
        assert _stable(out)

    def test_simple_case_value_wraps_with_its_paren_under_when(self):
        out, _ = format_sql(f"SELECT CASE a WHEN 1 THEN {self._LONG} ELSE 2 END AS v FROM t")
        assert "    WHEN 1 THEN (\n      SELECT\n" in out
        assert "\n    )\n    ELSE 2\n" in out
        assert _stable(out)
