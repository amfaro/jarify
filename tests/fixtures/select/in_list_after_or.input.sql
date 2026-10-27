-- A wrapped IN list after OR is indented under the OR, like one after AND
SELECT a FROM t WHERE a = 1 OR b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06')
;

-- A wrapped IN subquery after OR
SELECT a FROM t WHERE a = 1 OR b NOT IN (SELECT user_id FROM excluded_users WHERE excluded_reason = 'a long reason that pushes the subquery past the limit')
;

-- HAVING, after OR and after AND
SELECT a, COUNT(*) AS n FROM t GROUP BY ALL
HAVING COUNT(*) = 1 OR a IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06')
;

SELECT a, COUNT(*) AS n FROM t GROUP BY ALL
HAVING COUNT(*) = 1 AND a IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06')
;

-- A commented JOIN condition
SELECT a FROM t
INNER JOIN u ON u.a = t.a -- same account
OR u.b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06')
;

-- A CASE condition
SELECT
  CASE
    WHEN a = 1 OR b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06') THEN 'x'
    WHEN a = 2 THEN 'y'
  END AS z
FROM t
;

-- A parenthesized group after OR
SELECT a FROM t WHERE a = 1 OR (c = 2 AND b IN ('value_number_00', 'value_number_01', 'value_number_02', 'value_number_03', 'value_number_04', 'value_number_05', 'value_number_06'))
;
