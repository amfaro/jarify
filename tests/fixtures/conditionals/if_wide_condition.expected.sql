-- Wide boolean condition in CASE WHEN → rewritten to IF() on one line
SELECT
   if(s.transform IS NOT NULL AND s.transform.type = 'coverage', t.quantity / s.conversion_rate, t.quantity) AS coverage
FROM t
;

-- Very wide CASE WHEN → still IF() on one line (no CASE fallback)
SELECT
   if(
    some_really_long_column_name IS NOT NULL AND another_really_long_column_name.some_field = 'some_long_string_value_here'
   ,very_long_expression_name / another_quite_long_column_name
   ,fallback_to_this_column_name
  ) AS result
FROM t
;

-- IF() written directly with wide condition → must stay IF(), never rewrite to CASE WHEN
SELECT
   if(
    some_really_long_column_name IS NOT NULL AND another_really_long_column_name.some_field = 'some_long_string_value_here'
   ,very_long_expression_name / another_quite_long_column_name
   ,fallback_to_this_column_name
  ) AS result
FROM t
;
