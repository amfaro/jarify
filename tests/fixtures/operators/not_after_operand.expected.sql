-- NOT IN and NOT BETWEEN keep NOT after the operand, like NOT LIKE
SELECT
   a
FROM t
WHERE a NOT IN (SELECT b FROM u)
  AND c NOT LIKE 'x%'
  AND d NOT BETWEEN 1 AND 2
;

-- A NOT written in front is written after the operand too; parentheses keep it in front
SELECT
   a
FROM t
WHERE a NOT IN (1, 2)
  AND d NOT BETWEEN 1 AND 2
  AND NOT (b IN (3, 4))
;

-- The other negated predicates
SELECT
   a NOT IN (1, 2)          AS not_in
  ,b NOT BETWEEN 1 AND 3    AS not_between
  ,c NOT ILIKE 'a%'         AS not_ilike
  ,d NOT SIMILAR TO 'a.*'   AS not_similar
  ,e NOT GLOB 'a*'          AS not_glob
  ,f IS NOT DISTINCT FROM g AS not_distinct
  ,h IS NOT NULL            AS not_null
  ,NOT EXISTS (
    SELECT
       1
    FROM u
    WHERE u.a = t.a
  )                         AS not_exists
FROM t
;

-- In a JOIN condition, a FILTER and a CASE
SELECT
   CASE
     WHEN t.a NOT IN (1, 2)
     THEN 'x'
     WHEN t.b NOT BETWEEN 1 AND 2
     THEN 'y'
   END                                                             AS z
  ,COUNT(*) FILTER(WHERE t.day_name NOT IN ('Saturday', 'Sunday')) AS weekdays_count
FROM t
INNER JOIN u ON u.a = t.a AND u.b NOT IN (1, 2)
GROUP BY ALL
;

-- A long NOT IN list and a long NOT IN subquery
SELECT
   a
FROM t
WHERE country_code NOT IN (
   'NLD'
  ,'DEU'
  ,'POL'
  ,'ISR'
  ,'FRA'
  ,'GBR'
  ,'ITA'
  ,'ESP'
  ,'AUT'
  ,'BEL'
  ,'SWE'
  ,'CHE'
  ,'ROU'
  ,'CZE'
  ,'DNK'
  ,'PRT'
  ,'FIN'
  ,'HUN'
  ,'GRC'
  ,'UKR'
  ,'IRL'
  ,'NOR'
)
  AND user_id NOT IN
  (
    SELECT
       user_id
    FROM excluded_users
    WHERE excluded_reason = 'a long reason that pushes the subquery past the limit'
  )
;
