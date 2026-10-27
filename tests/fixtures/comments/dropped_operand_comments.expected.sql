-- Comments sqlglot dropped where it rebuilds a node are kept
SELECT
   a::my_type -- after the user-defined type
  ,b->>'key' -- after the JSON path
  ,list_filter(
     l
    ,lambda c: regexp_matches(c, 'x') -- at the end of the lambda body
  )                 AS matches
  ,INTERVAL '1' DAY -- after the interval
  ,(
     a.x
    ,a.y
  )::point_type     AS point
FROM t
;

-- A comment after a CASE, a window or EXISTS stays when one is written above it too
SELECT
   -- above the case
   CASE a
    WHEN 1 THEN 2
  END -- after the case
  -- above the window
  ,SUM(b) OVER (PARTITION BY c) -- after the window
  -- above exists
  ,EXISTS(
    SELECT
       1
    FROM u
  ) -- after exists
FROM t
;

-- A comment before = in a QUALIFY or an aligned WHERE condition stays
SELECT
   a
FROM t
WHERE a  = /* on the equals */ 1
  AND bb = 2
QUALIFY
  -- above the condition
  ROW_NUMBER() OVER (ORDER BY b) /* before the equals */ = 1
  AND a > 2
;

-- A comment on the comma of a comma join stays
SELECT
   a
FROM t
-- before the comma
CROSS JOIN u
;
