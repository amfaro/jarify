-- Wide boolean condition: compact IF() fits on one line → IF() is used
SELECT
  CASE WHEN s.transform IS NOT NULL AND s.transform.type = 'coverage' THEN t.quantity / s.conversion_rate ELSE t.quantity END AS coverage
FROM t
;

-- Very wide: exceeds max_line_length → CASE WHEN fallback
SELECT
  CASE
    WHEN some_really_long_column_name IS NOT NULL
     AND another_really_long_column_name.some_field = 'some_long_string_value_here'
    THEN very_long_expression_name / another_quite_long_column_name
    ELSE fallback_to_this_column_name
  END AS result
FROM t
;
