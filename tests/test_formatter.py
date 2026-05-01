"""Tests for the SQL formatter."""

from jarify.config import JarifyConfig
from jarify.formatter import format_sql


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
    lines = [line for line in result.splitlines() if " AS " in line]
    as_positions = [line.index(" AS ") for line in lines]
    assert len(set(as_positions)) == 1, f"AS keywords not aligned: {as_positions}"


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
    assert "\n   END        AS abc\n" in result


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
