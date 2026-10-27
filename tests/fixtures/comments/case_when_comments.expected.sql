-- Comments inside a multi-branch CASE WHEN condition
SELECT
   CASE
     WHEN a IS NOT NULL -- first
      AND b > 1 -- second
     THEN 1
     WHEN c > 0
       -- own line
       OR d > 0
     THEN 2
     ELSE 3
   END AS result
FROM t
;

-- A single-WHEN CASE with comments stays CASE instead of becoming IF()
SELECT
   CASE
     WHEN a IS NOT NULL -- first
      AND b > 1
     THEN 1
     ELSE 2
   END AS with_condition_comment
  ,CASE
     WHEN country = 'SER'
     THEN 'SRB' -- legacy code
     ELSE country
   END AS with_then_comment
FROM t
;
