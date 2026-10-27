-- A comment before a subquery's closing paren stays at the end of its body
SELECT
   s.a
FROM (
  SELECT
     a
  FROM t
  -- end of body
) AS s
LEFT JOIN (
  SELECT
     a
  FROM u
  -- end of the joined body
) AS w ON w.a = s.a
;

SELECT
   s.a
FROM (
  SELECT
     a
  FROM t
) AS s -- after the paren
;

-- Comments on if() are kept, as on any other call
SELECT
   -- above the call
   if(b = 1, 'x', 'y')          AS w
  ,if(a = 1, 'x', 'y')          AS v -- between the call and AS
  ,COUNT(*) FILTER(WHERE a = 1) AS n -- filtered
FROM t
;
