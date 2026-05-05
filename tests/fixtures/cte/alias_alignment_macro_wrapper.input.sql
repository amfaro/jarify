CREATE OR REPLACE MACRO example_macro(_op) AS TABLE
(
  WITH _wide AS
  (
    SELECT
       very_long_function_call(a, b, c) AS wide_result
      ,short                            AS x
    FROM t
  )
  ,_narrow AS
  (
    SELECT
       _wide.wide_result AS result
      ,_wide.x           AS letter
    FROM _wide
  )
  FROM _narrow
)
