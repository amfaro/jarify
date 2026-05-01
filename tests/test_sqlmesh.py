"""Tests for SQLMesh segmentation and runtime token masking."""

from jarify.sqlmesh import (
    looks_like_sqlmesh,
    mask_sqlmesh_runtime_tokens,
    split_sqlmesh_segments,
    unmask_sqlmesh_runtime_tokens,
)


def test_looks_like_sqlmesh_detects_known_markers():
    assert looks_like_sqlmesh("MODEL (name foo.bar);\nSELECT 1")
    assert looks_like_sqlmesh("AUDIT (name assert_positive);\nSELECT 1")
    assert looks_like_sqlmesh("ON_VIRTUAL_UPDATE_BEGIN;\nSELECT 1")
    assert looks_like_sqlmesh("JINJA_STATEMENT_BEGIN;\nSELECT 1\nJINJA_END;")
    assert looks_like_sqlmesh("SELECT * FROM @this_model WHERE ds >= @start_dt")
    assert looks_like_sqlmesh("SELECT * FROM @input_model WHERE ds = @run_dt")


def test_looks_like_sqlmesh_ignores_at_identifiers_in_strings_and_comments():
    sql = "SELECT '@run_dt' AS literal -- @input_model\n/* @block */"
    assert not looks_like_sqlmesh(sql)


def test_normal_sql_is_single_sql_segment_and_mask_noop():
    sql = "SELECT a, b FROM t WHERE ds > DATE '2025-01-01'"
    assert not looks_like_sqlmesh(sql)
    assert split_sqlmesh_segments(sql)[0].kind == "sql"
    assert split_sqlmesh_segments(sql)[0].text == sql
    masked, mapping = mask_sqlmesh_runtime_tokens(sql)
    assert masked == sql
    assert mapping == {}


def test_split_preserves_leading_model_header():
    sql = "MODEL (\n  name foo.bar,\n  kind FULL\n);\n\nselect a,b from t\n"
    segments = split_sqlmesh_segments(sql)
    assert [(s.kind, s.text) for s in segments] == [
        ("opaque", "MODEL (\n  name foo.bar,\n  kind FULL\n);\n\n"),
        ("sql", "select a,b from t\n"),
    ]


def test_split_header_ignores_parentheses_in_strings_and_comments():
    sql = (
        "MODEL (\n"
        "  name foo.bar,\n"
        "  description 'literal ) paren',\n"
        "  cron '@daily', -- comment )\n"
        "  owner (team)\n"
        ");\n"
        "SELECT 1\n"
    )
    segments = split_sqlmesh_segments(sql)
    assert segments[0].kind == "opaque"
    assert segments[0].text.startswith("MODEL (")
    assert segments[0].text.endswith(");\n")
    assert segments[1].text == "SELECT 1\n"


def test_split_virtual_update_markers_only():
    sql = "ON_VIRTUAL_UPDATE_BEGIN;\nselect a,b from t\nON_VIRTUAL_UPDATE_END;\n"
    segments = split_sqlmesh_segments(sql)
    assert [(s.kind, s.text) for s in segments] == [
        ("opaque", "ON_VIRTUAL_UPDATE_BEGIN;\n"),
        ("sql", "select a,b from t\n"),
        ("opaque", "ON_VIRTUAL_UPDATE_END;\n"),
    ]


def test_split_jinja_statement_marker_block_is_opaque():
    sql = "JINJA_STATEMENT_BEGIN;\nselect {{ x }}\nJINJA_END;\nselect 1\n"
    segments = split_sqlmesh_segments(sql)
    assert [(s.kind, s.text) for s in segments] == [
        ("opaque", "JINJA_STATEMENT_BEGIN;\nselect {{ x }}\nJINJA_END;\n"),
        ("sql", "select 1\n"),
    ]


def test_split_whole_line_jinja_control_block_is_opaque():
    sql = "select 1\n{% if is_incremental() %}\nselect * from raw\n{% endif %}\nselect 2\n"
    segments = split_sqlmesh_segments(sql)
    assert [(s.kind, s.text) for s in segments] == [
        ("sql", "select 1\n"),
        ("opaque", "{% if is_incremental() %}\nselect * from raw\n{% endif %}\n"),
        ("sql", "select 2\n"),
    ]


def test_mask_sqlmesh_runtime_tokens_round_trips_exactly():
    sql = "SELECT {{ ref('x') }} AS model_name FROM @this_model WHERE ds BETWEEN @start_dt AND @end_dt"
    masked, mapping = mask_sqlmesh_runtime_tokens(sql)
    assert "{{ ref('x') }}" not in masked
    assert "@this_model" not in masked
    assert "@start_dt" not in masked
    assert "@end_dt" not in masked
    assert unmask_sqlmesh_runtime_tokens(masked, mapping) == sql


def test_mask_sqlmesh_runtime_tokens_masks_arbitrary_at_identifiers_only_in_code():
    sql = (
        "SELECT @EACH(account_id) AS account_id FROM @input_model "
        "WHERE ds = @run_dt AND note = '@run_dt' -- @input_model\n"
        "/* @EACH */"
    )
    masked, mapping = mask_sqlmesh_runtime_tokens(sql)
    assert "@EACH(account_id)" not in masked
    assert "FROM @input_model" not in masked
    assert "ds = @run_dt" not in masked
    assert "note = '@run_dt'" in masked
    assert "-- @input_model" in masked
    assert "/* @EACH */" in masked
    assert unmask_sqlmesh_runtime_tokens(masked, mapping) == sql


def test_mask_sqlmesh_runtime_tokens_avoids_source_marker_collisions():
    sql = "SELECT __jsm0__ AS existing_marker, @run_dt AS run_dt"
    masked, mapping = mask_sqlmesh_runtime_tokens(sql)
    assert "@run_dt" not in masked
    assert "__jsm0__ AS existing_marker" in masked
    assert all(marker not in sql for marker in mapping)
    assert unmask_sqlmesh_runtime_tokens(masked, mapping) == sql
