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
        # Right-alignment: the END of each alias lands at the same column
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
        out, _ = format_sql("SELECT a, b, count(*) FROM t GROUP BY a, b")
        lines = out.splitlines()
        group_by_idx = next(i for i, line in enumerate(lines) if "GROUP BY" in line)
        # The line with GROUP BY should not contain column names on the same line
        group_by_line = lines[group_by_idx]
        assert group_by_line.strip() == "GROUP BY", f"Expected 'GROUP BY' on its own line, got: {group_by_line!r}"

    def test_group_by_all_stays_inline(self):
        out, _ = format_sql("SELECT a, b, count(*) FROM t GROUP BY ALL")
        assert "GROUP BY ALL" in out

    def test_group_by_single_column(self):
        out, _ = format_sql("SELECT a, count(*) FROM t GROUP BY a")
        assert "GROUP BY" in out
        assert "a" in out
