-- A wrapped condition after a CASE's first WHEN is laid out as after WHERE:
-- a list's values three columns past WHEN, and its closing ) under it
SELECT
  CASE WHEN b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06', 'value_number_07', 'value_number_08') THEN 1 WHEN c THEN 2 END AS v
FROM t
WHERE b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06', 'value_number_07', 'value_number_08')
;

-- an IN subquery, and parentheses
SELECT
  CASE WHEN b NOT IN (SELECT some_long_column_name_aaaaaaaa FROM some_long_table_name_bbbbbbbbbbbbb WHERE zz = 1 AND yy = 2 AND xx = 3) THEN 1 WHEN c THEN 2 END AS v
FROM t
WHERE b NOT IN (SELECT some_long_column_name_aaaaaaaa FROM some_long_table_name_bbbbbbbbbbbbb WHERE zz = 1 AND yy = 2 AND xx = 3)
;

SELECT
  CASE WHEN (x = 1 OR some_long_column_name_aaaaaaaa = some_long_table_name_bbbbbbbbbbbbb_cccccccc_dddddd_eeeeeeeeeee_ffffffffffffffff) THEN 1 WHEN c THEN 2 END AS v
FROM t
WHERE (x = 1 OR some_long_column_name_aaaaaaaa = some_long_table_name_bbbbbbbbbbbbb_cccccccc_dddddd_eeeeeeeeeee_ffffffffffffffff)
;

-- After AND or OR it goes under the connector, as after WHERE
SELECT
  CASE WHEN y = 2 AND b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06', 'value_number_07', 'value_number_08') THEN 1 WHEN y = 3 OR b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06', 'value_number_07', 'value_number_08') THEN 2 END AS v
FROM t
WHERE y = 2 AND b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06', 'value_number_07', 'value_number_08')
;
