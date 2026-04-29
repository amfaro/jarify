-- Wide boolean condition in CASE WHEN → rewritten to IF() on one line
SELECT
  CASE WHEN s.transform IS NOT NULL AND s.transform.type = 'coverage' THEN t.quantity / s.conversion_rate ELSE t.quantity END AS coverage
FROM t
;

-- Very wide CASE WHEN → still IF() on one line (no CASE fallback)
SELECT
  CASE
    WHEN some_really_long_column_name IS NOT NULL
     AND another_really_long_column_name.some_field = 'some_long_string_value_here'
    THEN very_long_expression_name / another_quite_long_column_name
    ELSE fallback_to_this_column_name
  END AS result
FROM t
;

-- IF() written directly with wide condition → must stay IF(), never rewrite to CASE WHEN
SELECT
  if(some_really_long_column_name IS NOT NULL AND another_really_long_column_name.some_field = 'some_long_string_value_here', very_long_expression_name / another_quite_long_column_name, fallback_to_this_column_name) AS result
FROM t
;

-- Wide IF() with an overlong true-expression → wrap nested branch expression too
SELECT
  CASE WHEN (ir.incentive_data->'transform'->>'type') IS NOT NULL THEN ((ir.incentive_data->'transform'->>'type'), (ir.incentive_data->'transform'->>'from'), (ir.incentive_data->'transform'->>'based_on'))::transform ELSE NULL END AS transform
;
